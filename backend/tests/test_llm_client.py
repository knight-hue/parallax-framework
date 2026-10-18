"""模型客户端 HTTP 失败语义测试。"""

import json

import httpx
import pytest
from pydantic import BaseModel

from parallax.config import Settings
from parallax.domain.errors import LLMError
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.ports.llm import ChatMessage


class _Reply(BaseModel):
    ok: bool


def test_openai_environment_aliases(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("PARALLAX_LLM_API_KEY", raising=False)
    monkeypatch.delenv("PARALLAX_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("PARALLAX_LLM_MODEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_api_key == "openai-key"
    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.llm_model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_reasoning_model_uses_openai_compatible_fields():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    client = OpenAICompatClient(
        Settings(llm_api_key="test", llm_model="gpt-6.1-sol", llm_max_retries=0),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.complete([ChatMessage(role="user", content="ping")], temperature=0, max_tokens=128)
    assert "temperature" not in captured
    assert captured["max_completion_tokens"] == 128
    await client.aclose()


@pytest.mark.asyncio
async def test_json_schema_instruction_is_a_leading_system_message():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    client = OpenAICompatClient(
        Settings(llm_api_key="test", llm_max_retries=0),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_json(
        [
            ChatMessage(role="system", content="domain rules"),
            ChatMessage(role="user", content="payload"),
        ],
        _Reply,
    )
    assert result.ok is True
    assert captured["messages"][0]["role"] == "system"
    assert "schema" in captured["messages"][0]["content"]
    assert captured["messages"][1]["role"] == "user"
    await client.aclose()


@pytest.mark.asyncio
async def test_payment_required_is_not_retried():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(402, request=request, text="quota exhausted")

    client = OpenAICompatClient(
        Settings(llm_api_key="test", llm_max_retries=3),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMError, match="402"):
        await client.complete([ChatMessage(role="user", content="ping")])
    assert calls == 1
    await client.aclose()
