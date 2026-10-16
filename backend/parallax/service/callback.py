"""完成回调：把一次运行的用量回报给 Java 网关。

## 为什么需要它

配额要在**提交前**校验，而真实 token 用量只有跑完才知道。两者靠
"提交时网关记一笔、完成时本服务补记用量"衔接。不回传的话，
网关的账本会长期停留在 0——报表和真实消耗对不上，配额也就失去了依据。

## 三条设计约束

1. **默认关闭**：`callback_url` 为空即不回调。脱离网关单独跑本服务时
   那个地址根本不存在，默认打开会让每次运行都白等一次超时。
2. **失败只记 WARN**：记账是平台层的事，绝不能反过来把一次成功的审查变成失败。
3. **不带凭据就不发**：网关没告诉我们是哪个凭据发起的调用时，
   回调没有归属可写，发过去只会得到 400。
"""

from __future__ import annotations

import json
import logging

import httpx

from parallax.config import Settings
from parallax.service.trace import current_trace_id

logger = logging.getLogger(__name__)

COMPLETE_PATH = "/api/v1/internal/runs/{run_id}/complete"


class CompletionCallback:
    """把运行结果回报给网关。"""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(self._settings.callback_url.strip())

    async def report(
        self,
        *,
        run_id: str,
        credential_id: str | None,
        status: str,
        prompt_tokens: int,
        completion_tokens: int,
        elapsed_s: float | None = None,
        stop_reason: str | None = None,
        counts: dict | None = None,
    ) -> bool:
        """上报一次运行的终态。返回是否上报成功；**从不抛异常**。"""
        if not self.enabled:
            return False
        if not credential_id:
            logger.debug("未收到凭据标识，跳过完成回调（run_id=%s）", run_id)
            return False

        url = self._settings.callback_url.rstrip("/") + COMPLETE_PATH.format(run_id=run_id)
        payload = {
            "credentialId": credential_id,
            "promptTokens": int(prompt_tokens),
            "completionTokens": int(completion_tokens),
            "status": status,
            "elapsedS": elapsed_s,
            "stopReason": stop_reason,
            "countsJson": json.dumps(counts or {}, ensure_ascii=False),
            "traceId": current_trace_id(),
        }
        headers = {}
        if self._settings.callback_token:
            headers["X-Internal-Token"] = self._settings.callback_token

        try:
            async with self._client_for() as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                # 记下响应体：网关的 4xx 里带着"哪一项不合法"，只看状态码无从排查
                logger.warning(
                    "完成回调被拒绝：HTTP %s %s（run_id=%s）",
                    response.status_code,
                    response.text[:200],
                    run_id,
                )
                return False
            logger.info("用量已回报给网关（run_id=%s，状态 %s）", run_id, status)
            return True
        except Exception as exc:  # noqa: BLE001 - 回调失败绝不影响运行结果
            logger.warning("完成回调失败（run_id=%s）：%s: %s", run_id, type(exc).__name__, exc)
            return False

    def _client_for(self) -> httpx.AsyncClient:
        if self._client is not None:
            return _BorrowedClient(self._client)
        return httpx.AsyncClient(timeout=self._settings.callback_timeout_s)


class _BorrowedClient:
    """包装外部传入的 client，使 `async with` 不会把它关掉。

    测试注入的 client 需要跨多次回调复用；直接 `async with` 会把它关闭，
    第二次回调就会在"client has been closed"上失败。
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *exc: object) -> bool:
        return False
