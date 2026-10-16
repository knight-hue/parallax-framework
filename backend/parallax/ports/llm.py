"""LLM 端口与调用预算。

`ReputationStore` 见 ports/stores.py。
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


@runtime_checkable
class LLMClient(Protocol):
    """模型客户端协议。

    之所以把 `complete_json` 单列：本框架的 Reader 必须产出结构化 claim，
    自由文本解析是可靠性最大的敌人。实现方需要负责
    「拿到合法 JSON 并过 schema 校验」，失败抛 SchemaValidationError 以便上层重试。
    """

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """返回纯文本补全。"""
        ...

    async def complete_json(
        self,
        messages: list[ChatMessage],
        schema: type[BaseModel],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> BaseModel:
        """返回已通过 schema 校验的实例。"""
        ...


class UsageStats(BaseModel):
    """调用统计——用于实验报告中的成本核算。"""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    failures: int = 0
    schema_retries: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Budget(BaseModel):
    """运行预算护栏。超出即停止补检循环（对应 RoundStopReason.BUDGET_EXHAUSTED）。"""

    max_llm_calls: int = 0
    """0 表示不限。"""
    max_tokens: int = 0
    used: UsageStats = Field(default_factory=UsageStats)

    def exhausted(self) -> bool:
        over_calls = bool(self.max_llm_calls) and self.used.calls >= self.max_llm_calls
        over_tokens = bool(self.max_tokens) and self.used.total_tokens >= self.max_tokens
        return over_calls or over_tokens
