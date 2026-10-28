"""OpenAI-compatible Chat Completions 客户端。

## 为什么自己写而不是套 LangChain 的 ChatModel

三个理由：
1. 本框架只需要两个能力（纯文本、受 schema 约束的 JSON），引入完整抽象收益为负；
2. `complete_json` 的**失败语义**必须由我们掌握——schema 校验失败要抛
   SchemaValidationError（可重试），网络失败要抛 LLMError（走退避），
   这两条路径的处置策略完全不同，藏进第三方抽象里就没法精确控制；
3. 依赖更少，评委和读者都能直接读懂。

## 可靠性处理

- 429 / 5xx / 连接异常：指数退避重试（`llm_max_retries`）
- 4xx（除 429）：立即失败，重试无意义
- JSON 提取：容忍 markdown 围栏与前后废话（真实模型经常画蛇添足）
- 校验失败：抛 SchemaValidationError，交由 ReaderPool 决定是否重问
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from parallax.config import Settings
from parallax.domain.errors import ConfigurationError, LLMError, SchemaValidationError
from parallax.infra.provider import build_body, resolve_profile
from parallax.ports.llm import ChatMessage, UsageStats

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

_JSON_INSTRUCTION = (
    "你必须只输出一个合法 JSON 对象，不要输出任何解释文字、不要使用 markdown 代码围栏。"
    "JSON 必须严格满足以下 schema：\n{schema}"
)


class OpenAICompatClient:
    """OpenAI 兼容 /chat/completions 客户端。"""

    def __init__(
        self,
        settings: Settings,
        usage: UsageStats | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.llm_api_key:
            raise ConfigurationError(
                "未配置模型 API Key（PARALLAX_LLM_API_KEY 或 OPENAI_API_KEY）。"
                "若只是跑单测/对照实验，请使用 FakeLLMClient。"
            )
        self.settings = settings
        self.usage = usage or UsageStats()
        self.profile = resolve_profile(settings)
        self._client = client
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # ---- 协议实现 ----

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        payload = await self._post(messages, temperature, max_tokens, json_mode=False)
        return self._extract_text(payload)

    async def complete_json(
        self,
        messages: list[ChatMessage],
        schema: type[BaseModel],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> BaseModel:
        instruction = _JSON_INSTRUCTION.format(
            schema=json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        )
        # System instructions must precede user messages.  Appending a system
        # message after the user prompt is accepted by some compatible servers
        # but ignored or rejected by others.
        instructed = list(messages)
        system_index = next(
            (index for index, message in enumerate(instructed) if message.role == "system"),
            None,
        )
        if system_index is None:
            instructed.insert(0, ChatMessage(role="system", content=instruction))
        else:
            current = instructed[system_index]
            instructed[system_index] = ChatMessage(
                role="system", content=f"{current.content}\n\n{instruction}"
            )
        payload = await self._post(instructed, temperature, max_tokens, json_mode=True)
        raw = self._extract_text(payload)
        try:
            return schema.model_validate(self._loads(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            raise SchemaValidationError(
                f"模型输出不满足 {schema.__name__}: {exc}; raw_head={raw[:400]!r}"
            ) from exc

    # ---- 内部 ----

    async def _post(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        *,
        json_mode: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = build_body(
            self.profile,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            use_json_mode=self.settings.llm_use_json_mode,
            reasoning_effort=self.settings.llm_reasoning_effort,
        )

        url = self.profile.chat_completions_url
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                client = await self._ensure_client()
                response = await asyncio.wait_for(
                    client.post(url, json=body, headers=headers),
                    timeout=self.settings.llm_timeout_s,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                if response.status_code >= 400:
                    raise LLMError(
                        f"模型返回 {response.status_code}（不可重试）：{response.text[:400]}"
                    )
                data = response.json()
                self._record_usage(data)
                self.usage.calls += 1
                return data
            except LLMError:
                raise
            except (
                httpx.HTTPStatusError,
                httpx.TransportError,
                httpx.TimeoutException,
                TimeoutError,
            ) as exc:
                last_error = exc
                self.usage.failures += 1
                if attempt >= self.settings.llm_max_retries:
                    break
                logger.warning(
                    "模型调用失败（第 %d 次），%.1fs 后重试：%s", attempt + 1, delay, exc
                )
                await asyncio.sleep(delay)
                delay *= 2
            except (json.JSONDecodeError, KeyError) as exc:
                raise LLMError(f"响应体不可解析：{exc}") from exc

        raise LLMError(f"模型调用重试耗尽：{last_error}")

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        """保留给旧调用方；新代码请用 provider.resolve_profile。"""
        normalized = model.casefold().strip()
        return normalized.startswith(("o1", "o3", "o4", "gpt-5", "gpt-6"))

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.llm_timeout_s)
            self._owns_client = True
        return self._client

    def _record_usage(self, data: dict[str, Any]) -> None:
        usage = data.get("usage") or {}
        self.usage.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.usage.completion_tokens += int(usage.get("completion_tokens") or 0)

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"响应中没有 choices：{str(data)[:300]}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            raise LLMError("响应中没有 content 字段")
        if not content.strip():
            # 推理型模型（如 DeepSeek flash 系列）会把输出预算先花在 reasoning_content 上，
            # max_tokens 太小时 content 会是空字符串。这种情况必须显式报错，
            # 否则空串会一路走到 JSON 解析，变成一次没有信息量的 schema 重试。
            reasoning = message.get("reasoning_content") or ""
            finish = choices[0].get("finish_reason")
            raise LLMError(
                "模型返回了空 content"
                f"（finish_reason={finish!r}，reasoning_content 长度={len(reasoning)}）。"
                "推理型模型需要更大的 max_tokens。"
            )
        return content

    @staticmethod
    def _loads(raw: str) -> Any:
        """从可能带围栏/废话的文本里抠出 JSON。"""
        text = raw.strip()
        fenced = _FENCE_RE.search(text)
        if fenced:
            text = fenced.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
