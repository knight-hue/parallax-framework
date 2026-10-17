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
                "未配置 PARALLAX_LLM_API_KEY。若只是跑单测/对照实验，请使用 FakeLLMClient。"
            )
        self.settings = settings
        self.usage = usage or UsageStats()
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
        instructed = [
            *messages,
            ChatMessage(
                role="system",
                content=_JSON_INSTRUCTION.format(
                    schema=json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
                ),
            ),
        ]
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
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if json_mode and self.settings.llm_use_json_mode:
            body["response_format"] = {"type": "json_object"}

        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                client = await self._ensure_client()
                response = await client.post(url, json=body, headers=headers)
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
            except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException) as exc:
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
