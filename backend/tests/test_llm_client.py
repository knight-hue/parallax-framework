"""模型客户端 HTTP 失败语义测试。"""

import httpx
import pytest

from parallax.config import Settings
from parallax.domain.errors import LLMError
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.ports.llm import ChatMessage


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
