"""模型供应商差异层。

## 为什么要单独一层

"OpenAI 兼容"只保证路径和响应形状相似，不保证**参数**一致：

- OpenAI 的推理模型（o 系列、GPT-5/6）不接受 `temperature`，且推荐 `max_completion_tokens`；
- DeepSeek 的 `reasoner` 类模型同样不接受采样参数，也没有 `reasoning_effort` 字段；
- 部分兼容端点接受 `response_format=json_object`，部分直接 400。

把这些差异写进客户端主流程会让 main path 变成一堆 if。抽出一层后，
客户端只负责传输与重试，参数差异由 profile 决定。

## 设计约束

- **不猜测**：只有明确的规则才改请求体；拿不准就不发该字段。
- **可覆盖**：`PARALLAX_LLM_PROVIDER` 显式指定时优先于按域名推断。
- **不锁死**：默认 base_url / model 只在"供应商被显式指定且用户没改默认值"时才替换。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

ProviderName = Literal["openai", "openai_compat", "deepseek"]

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": OPENAI_DEFAULT_BASE_URL,
    "deepseek": "https://api.deepseek.com",
}

DEFAULT_MODELS: dict[str, str] = {
    "openai": OPENAI_DEFAULT_MODEL,
    "deepseek": "deepseek-chat",
}

_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")
_DEEPSEEK_REASONING_MARKERS = ("reasoner", "reasoning", "-r1", "think")


@dataclass(frozen=True)
class ProviderProfile:
    """一次运行使用的有效供应商参数。"""

    name: ProviderName
    base_url: str
    model: str
    reasoning: bool
    send_temperature: bool
    send_reasoning_effort: bool
    send_json_mode: bool
    token_field: str

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


def detect_provider(base_url: str, explicit: str = "auto") -> ProviderName:
    """显式配置优先；否则按域名推断，默认按 OpenAI 处理。"""
    choice = (explicit or "auto").strip().lower()
    if choice != "auto":
        if choice in {"openai", "openai_compat", "deepseek"}:
            return choice  # type: ignore[return-value]
        raise ValueError(f"未知的模型供应商：{explicit}")
    host = (urlparse(base_url).hostname or "").lower()
    if "deepseek" in host:
        return "deepseek"
    if host in {"api.openai.com", "openai.com"}:
        return "openai"
    return "openai_compat"


def is_reasoning_model(provider: ProviderName, model: str) -> bool:
    normalized = (model or "").casefold().strip()
    if provider == "deepseek":
        return any(marker in normalized for marker in _DEEPSEEK_REASONING_MARKERS)
    return normalized.startswith(_REASONING_PREFIXES)


def resolve_profile(settings: Any) -> ProviderProfile:
    """把配置折算成一份可执行的供应商参数。

    只在"显式指定供应商 + 用户没改默认值"时替换 base_url/model，
    避免悄悄把一个手写的自定义端点改掉。
    """
    explicit = getattr(settings, "llm_provider", "auto") or "auto"
    base_url = (settings.llm_base_url or "").strip()
    provider = detect_provider(base_url or OPENAI_DEFAULT_BASE_URL, explicit)

    if provider == "deepseek" and (
        not base_url or base_url.rstrip("/") == OPENAI_DEFAULT_BASE_URL.rstrip("/")
    ):
        base_url = DEFAULT_BASE_URLS["deepseek"]
    if not base_url:
        base_url = DEFAULT_BASE_URLS.get(provider, OPENAI_DEFAULT_BASE_URL)

    model = (settings.llm_model or "").strip()
    if not model or model == OPENAI_DEFAULT_MODEL and provider != "openai":
        model = DEFAULT_MODELS.get(provider, OPENAI_DEFAULT_MODEL)

    reasoning = is_reasoning_model(provider, model)
    # 显式声明优先于按名字猜：名字盖不住所有命名，而分类会改变请求体形状。
    override = getattr(settings, "llm_reasoning", None)
    if override is not None:
        reasoning = bool(override)
    return ProviderProfile(
        name=provider,
        base_url=base_url,
        model=model,
        reasoning=reasoning,
        send_temperature=not reasoning,
        # `reasoning_effort` 是 OpenAI 专有字段，DeepSeek 不接受，兼容端点也不保证支持。
        send_reasoning_effort=provider in {"openai", "openai_compat"},
        send_json_mode=not (provider == "deepseek" and reasoning),
        token_field="max_tokens"
        if provider == "deepseek"
        else ("max_completion_tokens" if reasoning else "max_tokens"),
    )


def build_body(
    profile: ProviderProfile,
    messages: list[Any],
    *,
    temperature: float,
    max_tokens: int | None,
    json_mode: bool,
    use_json_mode: bool,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    """构造 /chat/completions 请求体。纯函数，便于单测。"""
    body: dict[str, Any] = {
        "model": profile.model,
        "messages": [message.model_dump() for message in messages],
    }
    if profile.send_temperature:
        body["temperature"] = temperature
    if reasoning_effort is not None and profile.send_reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    if max_tokens:
        body[profile.token_field] = max_tokens
    if json_mode and use_json_mode and profile.send_json_mode:
        body["response_format"] = {"type": "json_object"}
    return body
