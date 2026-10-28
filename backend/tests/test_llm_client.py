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


async def test_request_has_total_deadline_even_when_transport_never_finishes():
    import asyncio

    async def handler(request):
        await asyncio.sleep(10)
        return httpx.Response(200, json={})

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenAICompatClient(
        Settings(llm_api_key="test", llm_timeout_s=0.05, llm_max_retries=0), client=transport
    )
    try:
        with pytest.raises(LLMError):
            await asyncio.wait_for(client.complete([ChatMessage(role="user", content="test")]), 1)
        assert client.usage.failures == 1
    finally:
        await transport.aclose()


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
        Settings(
            _env_file=None,
            llm_api_key="test",
            llm_model="gpt-6.1-sol",
            llm_base_url="https://api.openai.com/v1",
            llm_max_retries=0,
        ),
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


def test_empty_optional_reasoning_setting_is_omitted():
    from parallax.config import Settings

    assert Settings(_env_file=None, llm_reasoning_effort="").llm_reasoning_effort is None


@pytest.mark.asyncio
async def test_empty_content_from_reasoning_model_is_reported_as_error():
    """推理模型把预算花在 reasoning_content 上时，content 会是空串——必须显式报错。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "思考中",
                        },
                    }
                ]
            },
        )

    client = OpenAICompatClient(
        Settings(_env_file=None, llm_api_key="test", llm_max_retries=0),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMError) as excinfo:
        await client.complete([ChatMessage(role="user", content="ping")], max_tokens=16)
    message = str(excinfo.value)
    assert "空 content" in message
    assert "finish_reason" in message
    assert "max_tokens" in message
    await client.aclose()


def test_parallax_api_key_wins_over_openai_api_key(monkeypatch):
    """两个密钥都填时必须用 PARALLAX 的，不能把旧供应商的密钥发到新端点。"""
    from parallax.config import Settings

    monkeypatch.setenv("PARALLAX_LLM_API_KEY", "parallax-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key-longer")
    settings = Settings(_env_file=None)

    assert settings.llm_api_key == "parallax-key"
    assert settings.api_key_source == "PARALLAX_LLM_API_KEY"


def test_openai_key_is_used_when_parallax_key_is_empty(monkeypatch):
    from parallax.config import Settings

    monkeypatch.setenv("PARALLAX_LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-fallback")
    settings = Settings(_env_file=None)

    assert settings.llm_api_key == "openai-fallback"
    assert settings.api_key_source == "OPENAI_API_KEY"
