"""离线假模型客户端。

存在的意义不是"图省事"，而是让**核心机制可以脱离外部依赖被验证**：
单测要能断言账本、聚合规则、覆盖率判断的行为，这些都不该依赖网络和大模型。
同时它也是对照实验里"固定返回"那一组的实现基础。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from parallax.domain.errors import LLMError, SchemaValidationError
from parallax.ports.llm import ChatMessage, UsageStats

Responder = Callable[[list[ChatMessage]], Any]


class FakeLLMClient:
    """按回调脚本产出结果。

    `responder` 返回 dict（会被 schema 校验）或 BaseModel 实例。
    若返回异常对象，则直接抛出——用于模拟 schema 失败与网络失败。
    """

    def __init__(
        self,
        responder: Responder | None = None,
        usage: UsageStats | None = None,
    ) -> None:
        self.responder = responder or (lambda _messages: {})
        self.usage = usage or UsageStats()
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(list(messages))
        self.usage.calls += 1
        result = self.responder(messages)
        if isinstance(result, Exception):
            raise result
        return str(result)

    async def complete_json(
        self,
        messages: list[ChatMessage],
        schema: type[BaseModel],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> BaseModel:
        self.calls.append(list(messages))
        self.usage.calls += 1
        result = self.responder(messages)
        if isinstance(result, Exception):
            if isinstance(result, SchemaValidationError):
                self.usage.schema_retries += 1
            else:
                self.usage.failures += 1
            raise result
        if isinstance(result, BaseModel):
            return result
        try:
            return schema.model_validate(result)
        except Exception as exc:  # noqa: BLE001
            self.usage.schema_retries += 1
            raise SchemaValidationError(str(exc)) from exc


class RecordingLLMClient(FakeLLMClient):
    """额外记录「每次调用时看到的证据」，用于断言盲读隔离。

    判据很直接：任意两个 Reader 调用里出现的证据片段集合，
    不应包含另一个 Reader 的 claim 文本。
    """

    def __init__(self, responder: Responder | None = None, usage: UsageStats | None = None) -> None:
        super().__init__(responder, usage)
        self.payloads: list[str] = []

    async def complete_json(
        self,
        messages: list[ChatMessage],
        schema: type[BaseModel],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> BaseModel:
        self.payloads.append("\n".join(m.content for m in messages))
        return await super().complete_json(
            messages, schema, temperature=temperature, max_tokens=max_tokens
        )

    def payload_for(self, index: int) -> str:
        return self.payloads[index]


def always_fail(error: Exception | None = None) -> FakeLLMClient:
    """总是失败的客户端，用于测试失败路径。"""
    err = error or LLMError("simulated failure")
    return FakeLLMClient(responder=lambda _m: err)


def constant(payload: dict[str, Any]) -> FakeLLMClient:
    """恒定返回同一份 payload 的客户端。"""
    return FakeLLMClient(responder=lambda _m: payload)
