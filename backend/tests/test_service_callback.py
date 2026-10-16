"""完成回调与链路追踪。

回调是"Python 编排层"与"Java 平台层"之间唯一的写通道，因此它必须满足三条：
**默认关闭**、**失败不影响运行结果**、**不带凭据就不发**。
本文件逐条验证，不依赖网络（用 httpx 的 MockTransport）。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from parallax.infra.llm_fake import FakeLLMClient
from parallax.service.app import create_app
from parallax.service.callback import CompletionCallback
from parallax.service.trace import (
    CREDENTIAL_HEADER,
    TRACE_HEADER,
    TraceLogFilter,
    current_trace_id,
    set_trace_id,
)
from tests.conftest import make_settings

CREDENTIAL = "cred-1234"


def recording_transport(seen: list[httpx.Request], *, status: int = 200):
    """记录请求并返回固定状态码的传送层。"""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={"ok": status < 400})

    return httpx.MockTransport(handler)


def callback_with(seen: list[httpx.Request], **overrides) -> CompletionCallback:
    settings = make_settings(callback_url="http://gw.test", **overrides)
    return CompletionCallback(
        settings, client=httpx.AsyncClient(transport=recording_transport(seen))
    )


def parse(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


# ──────────────────────────── 开关 ────────────────────────────


async def test_disabled_by_default_sends_nothing():
    seen: list[httpx.Request] = []
    settings = make_settings()  # callback_url 默认为空
    assert settings.callback_url == ""

    callback = CompletionCallback(
        settings, client=httpx.AsyncClient(transport=recording_transport(seen))
    )
    sent = await callback.report(
        run_id="r1", credential_id=CREDENTIAL, status="done", prompt_tokens=1, completion_tokens=1
    )
    assert sent is False
    assert seen == [], "未配置回调地址时不应该发出任何请求"


async def test_missing_credential_skips_callback():
    seen: list[httpx.Request] = []
    callback = callback_with(seen)

    sent = await callback.report(
        run_id="r1", credential_id=None, status="done", prompt_tokens=1, completion_tokens=1
    )
    assert sent is False
    assert seen == [], "没有归属人时发过去只会得到 400，不如不发"


# ──────────────────────────── 载荷 ────────────────────────────


async def test_payload_carries_usage_status_and_trace():
    seen: list[httpx.Request] = []
    callback = callback_with(seen, callback_token="internal-token")
    set_trace_id("trace-abc")

    sent = await callback.report(
        run_id="run-9",
        credential_id=CREDENTIAL,
        status="done",
        prompt_tokens=1200,
        completion_tokens=300,
        elapsed_s=42.5,
        stop_reason="max_rounds_reached",
        counts={"high_confidence": 3, "pending": 7},
    )

    assert sent is True
    assert len(seen) == 1
    request = seen[0]
    assert request.url.path == "/api/v1/internal/runs/run-9/complete"
    assert request.headers["X-Internal-Token"] == "internal-token"

    body = parse(request)
    assert body["credentialId"] == CREDENTIAL
    assert body["promptTokens"] == 1200
    assert body["completionTokens"] == 300
    assert body["status"] == "done"
    assert body["elapsedS"] == 42.5
    assert body["stopReason"] == "max_rounds_reached"
    assert json.loads(body["countsJson"]) == {"high_confidence": 3, "pending": 7}
    assert body["traceId"] == "trace-abc", "traceId 必须回传，否则两端日志对不上同一次请求"


async def test_total_tokens_are_not_sent_so_server_stays_authoritative():
    seen: list[httpx.Request] = []
    callback = callback_with(seen)
    await callback.report(
        run_id="r", credential_id=CREDENTIAL, status="done", prompt_tokens=10, completion_tokens=5
    )
    assert "totalTokens" not in parse(seen[0]), "合计由服务端算，客户端不该提供第二个事实来源"


# ──────────────────────────── 失败路径 ────────────────────────────


async def test_rejected_callback_returns_false_without_raising():
    seen: list[httpx.Request] = []
    settings = make_settings(callback_url="http://gw.test")
    client = httpx.AsyncClient(transport=recording_transport(seen, status=400))
    callback = CompletionCallback(settings, client=client)

    sent = await callback.report(
        run_id="r", credential_id=CREDENTIAL, status="done", prompt_tokens=1, completion_tokens=1
    )
    assert sent is False, "网关拒绝时应如实返回 False，而不是假装成功"


async def test_network_failure_is_swallowed():
    """回调失败绝不能让一次成功的审查变成失败。"""

    def explode(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    settings = make_settings(callback_url="http://gw.test")
    callback = CompletionCallback(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(explode))
    )

    sent = await callback.report(
        run_id="r", credential_id=CREDENTIAL, status="done", prompt_tokens=1, completion_tokens=1
    )
    assert sent is False


# ──────────────────────────── 端到端 ────────────────────────────


def _tiny_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    return repo


def test_trace_and_credential_headers_reach_meta_json(tmp_path: Path):
    seen: list[httpx.Request] = []
    settings = make_settings(callback_url="http://gw.test")
    app = create_app(
        settings,
        runs_dir=tmp_path / "runs",
        client_factory=lambda _s: FakeLLMClient(responder=lambda _m: {"findings": []}),
    )
    # 把回调客户端换成一个"记录请求"的实例，避免真的发网络请求
    app.state.runner._callback = CompletionCallback(
        settings, client=httpx.AsyncClient(transport=recording_transport(seen))
    )

    # ⚠️ 必须先离开 `with` 块再读 meta.json。
    # TestClient 在退出时走 lifespan shutdown → `runner.shutdown()` 会等后台任务收敛；
    # 在 `with` 里面读，后台任务可能正写到一半，读到的是**空文件**。
    # 这个竞态在本地 3.13 上没暴露，在 CI 的 3.11/3.12 上稳定复现。
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/audits",
            json={"repo_path": str(_tiny_repo(tmp_path))},
            headers={TRACE_HEADER: "trace-e2e", CREDENTIAL_HEADER: CREDENTIAL},
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

    meta = json.loads((tmp_path / "runs" / run_id / "meta.json").read_text(encoding="utf-8"))
    assert meta["trace_id"] == "trace-e2e", "traceId 必须落到 meta.json，供事后对齐两端日志"
    assert meta["credential_id"] == CREDENTIAL
    assert meta["status"] == "done"

    assert len(seen) == 1, "运行结束必须回报一次用量"
    body = parse(seen[0])
    assert body["traceId"] == "trace-e2e"
    assert body["credentialId"] == CREDENTIAL
    assert body["status"] == "done"


def test_submit_without_gateway_headers_still_works(tmp_path: Path):
    """不经网关直接调本服务时不应有任何变化——回调默认关闭，头也可以不带。"""
    app = create_app(
        make_settings(),
        runs_dir=tmp_path / "runs",
        client_factory=lambda _s: FakeLLMClient(responder=lambda _m: {"findings": []}),
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/audits", json={"repo_path": str(_tiny_repo(tmp_path))})
        assert response.status_code == 202
        run_id = response.json()["run_id"]

    meta = json.loads((tmp_path / "runs" / run_id / "meta.json").read_text(encoding="utf-8"))
    assert meta["trace_id"] is None
    assert meta["credential_id"] is None


# ──────────────────────────── 日志注入 ────────────────────────────


def test_log_filter_injects_trace_id():
    import logging

    record = logging.LogRecord("parallax.x", logging.INFO, __file__, 1, "hi", None, None)
    set_trace_id("trace-42")
    assert TraceLogFilter().filter(record) is True
    assert record.trace_id == "trace-42"

    set_trace_id(None)
    assert TraceLogFilter().filter(record) is True
    assert record.trace_id == "-", "没有 traceId 时也要有占位符，否则格式化会取到缺失字段"


def test_trace_context_is_per_task_not_global():
    """ContextVar 而不是线程局部变量：并发运行的多个任务不能互相覆盖 traceId。"""
    import asyncio

    async def scenario() -> tuple[str | None, str | None]:
        set_trace_id("trace-A")
        other = asyncio.create_task(capture())
        mine = current_trace_id()
        return mine, await other

    async def capture() -> str | None:
        # 子任务继承的是**创建时**的上下文副本
        return current_trace_id()

    assert asyncio.run(scenario()) == ("trace-A", "trace-A")


# ──────────────────────────── 持久化 ────────────────────────────


def test_meta_write_is_atomic(tmp_path: Path):
    """`meta.json` 的写入必须是"要么旧内容、要么新内容"，不能有空的中间态。

    直接 `write_text` 会先清空再写，读者在两者之间会读到**空文件**。
    这个竞态在 CI 的 Python 3.11/3.12 上稳定复现过（本地 3.13 碰不到），
    表现为 `json.loads("")` 抛 JSONDecodeError。
    """
    from parallax.service.store import RunRecord, RunStore

    store = RunStore(tmp_path / "runs")
    store.create(RunRecord(run_id="r1", status="queued", repo_path="/x"))

    meta_path = store.run_dir("r1") / "meta.json"
    assert meta_path.exists()

    store.update("r1", status="done")
    assert json.loads(meta_path.read_text(encoding="utf-8"))["status"] == "done"
    assert not (store.run_dir("r1") / "meta.json.tmp").exists(), "临时文件必须被替换掉，不能残留"
