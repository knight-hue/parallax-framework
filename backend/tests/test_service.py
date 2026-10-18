"""服务层测试：事件总线、运行编排、HTTP 端点。

全部使用假模型客户端 + 临时 runs 目录，**不需要网络、不烧 API 额度、不污染真实运行记录**。
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parallax.infra.llm_fake import FakeLLMClient
from parallax.ports.llm import UsageStats
from parallax.service.app import create_app
from parallax.service.events import RunEventBus
from parallax.service.runner import AuditRunner
from parallax.service.store import RunRecord, RunStore
from tests.conftest import make_responder, make_settings

# ──────────────────────────── 事件总线 ────────────────────────────


def test_publish_assigns_monotonic_sequence():
    bus = RunEventBus()
    a = bus.publish("r1", "one", {"x": 1})
    b = bus.publish("r1", "two")
    assert (a.seq, b.seq) == (1, 2)
    assert b.payload == {}


def test_history_supports_replay_cursor():
    """断线重连靠 it 补发缺口——这是 SSE 能"续上"的关键。"""
    bus = RunEventBus()
    for i in range(5):
        bus.publish("r1", "tick", {"i": i})

    assert len(bus.history("r1")) == 5
    replayed = bus.history("r1", after_seq=3)
    assert [e.payload["i"] for e in replayed] == [3, 4]


def test_history_is_isolated_per_run():
    bus = RunEventBus()
    bus.publish("r1", "a")
    bus.publish("r2", "b")
    assert [e.type for e in bus.history("r1")] == ["a"]
    assert [e.type for e in bus.history("r2")] == ["b"]
    assert bus.history("missing") == []


def test_event_journal_survives_bus_restart(tmp_path: Path):
    """生产模式重启事件总线后，SSE 仍可重放历史事件。"""
    journal = tmp_path / "runs"
    first = RunEventBus(journal)
    first.publish("r1", "queued", {"n": 1})
    first.publish("r1", "done", {"n": 2})
    first.close("r1")

    restarted = RunEventBus(journal)
    assert [event.type for event in restarted.history("r1")] == ["queued", "done"]
    assert restarted.history("r1", after_seq=1)[0].payload == {"n": 2}
    assert restarted.is_closed("r1")
    recovered = restarted.publish("r1", "recovered")
    assert recovered.seq == 3
    assert [event.seq for event in restarted.history("r1")] == [1, 2, 3]


async def test_subscriber_receives_live_events_then_sentinel():
    bus = RunEventBus()
    queue = bus.subscribe("r1")
    bus.publish("r1", "hello")
    assert (await asyncio.wait_for(queue.get(), 1)).type == "hello"

    bus.close("r1")
    assert await asyncio.wait_for(queue.get(), 1) is None, "关闭后必须发出终止哨兵"
    assert bus.is_closed("r1")


def test_unsubscribe_stops_delivery():
    bus = RunEventBus()
    queue = bus.subscribe("r1")
    bus.unsubscribe("r1", queue)
    bus.publish("r1", "nobody-listening")
    assert queue.empty()
    assert bus.subscriber_count("r1") == 0


def test_sse_wire_format_uses_event_type_and_id():
    bus = RunEventBus()
    event = bus.publish("r1", "coverage", {"fill": 0.5})
    wire = event.to_sse()
    assert wire.startswith(f"id: {event.seq}\n")
    assert "event: coverage\n" in wire
    assert wire.endswith("\n\n"), "SSE 事件必须以空行结束"
    assert json.loads(wire.split("data: ", 1)[1].strip()) == {"fill": 0.5}


# ──────────────────────────── 运行存储 ────────────────────────────


def test_store_roundtrip(tmp_path: Path):
    store = RunStore(tmp_path / "runs")
    store.create(RunRecord(run_id="abc", question="q", repo_path="/x"))
    assert store.get("abc").question == "q"

    store.update("abc", status="done", counts={"high_confidence": 2})
    record = store.get("abc")
    assert record.status == "done" and record.counts["high_confidence"] == 2

    store.save_report("abc", "# 报告")
    assert store.read_report("abc") == "# 报告"
    assert store.get("nope") is None


def test_store_list_is_newest_first(tmp_path: Path):
    store = RunStore(tmp_path / "runs")
    store.create(RunRecord(run_id="old", created_at="2026-01-01T00:00:00+00:00"))
    store.create(RunRecord(run_id="new", created_at="2026-12-31T00:00:00+00:00"))
    assert [r.run_id for r in store.list()] == ["new", "old"]


def test_store_claim_is_cross_process_safe_and_releasable(tmp_path: Path):
    store = RunStore(tmp_path / "runs")
    store.create(RunRecord(run_id="claim-me"))
    other_view = RunStore(tmp_path / "runs")
    assert store.claim("claim-me") is True
    assert other_view.claim("claim-me") is False
    assert store.lease_active("claim-me") is True
    store.release("claim-me")
    assert other_view.claim("claim-me") is True


# ──────────────────────────── 编排执行 ────────────────────────────


async def test_runner_executes_persists_and_emits(tmp_path: Path, demo_repo, defects):
    store = RunStore(tmp_path / "runs")
    bus = RunEventBus()
    runner = AuditRunner(
        store,
        bus,
        make_settings(max_rounds=2),
        client_factory=lambda _s: FakeLLMClient(make_responder(defects)),
    )

    record = runner.submit(repo_path=str(demo_repo), overrides={})
    await runner.shutdown()

    saved = store.get(record.run_id)
    assert saved is not None and saved.status == "done", saved.error if saved else None
    assert saved.counts.get("high_confidence", 0) >= 1
    assert saved.elapsed_s is not None and saved.elapsed_s >= 0
    assert store.read_report(record.run_id)
    assert store.read_summary(record.run_id)["coverage"]["rows"]

    types = [e.type for e in bus.history(record.run_id)]
    assert types[0] == "queued"
    for expected in (
        "started",
        "ingest",
        "partition",
        "reader",
        "collect",
        "aggregate",
        "coverage",
        "done",
    ):
        assert expected in types, f"缺少事件 {expected}（实际：{types}）"
    assert bus.is_closed(record.run_id)


async def test_runner_reuses_persistent_reputation_across_instances(
    tmp_path: Path, demo_repo, defects
):
    """同一 runs 目录重启服务后，Reader 声誉仍可用于下一次审查。"""
    runs = tmp_path / "runs"
    first_store = RunStore(runs)
    first = AuditRunner(
        first_store,
        RunEventBus(runs),
        make_settings(max_rounds=1),
        client_factory=lambda _s: FakeLLMClient(make_responder(defects)),
    )
    record = first.submit(repo_path=str(demo_repo), overrides={})
    await first.shutdown()
    first_scores = first._reputation_store.scores()  # noqa: SLF001
    assert first_scores

    second = AuditRunner(
        RunStore(runs),
        RunEventBus(runs),
        make_settings(max_rounds=1),
        client_factory=lambda _s: FakeLLMClient(make_responder(defects)),
    )
    assert second._reputation_store.scores() == first_scores  # noqa: SLF001
    assert record.run_id


async def test_runner_report_and_summary_use_the_store_run_id(tmp_path: Path, demo_repo, defects):
    """报告/结果里的 run_id 必须就是运行记录的 run_id。

    引擎默认会按配置自行派生一个 id，若服务层不显式传入，
    报告标题里就会出现一个"查不到运行记录"的 id——这是排查线上问题时的噩梦。
    """
    store = RunStore(tmp_path / "runs")
    bus = RunEventBus()
    runner = AuditRunner(
        store,
        bus,
        make_settings(max_rounds=1),
        client_factory=lambda _s: FakeLLMClient(make_responder(defects)),
    )

    record = runner.submit(repo_path=str(demo_repo), overrides={})
    await runner.shutdown()

    report = store.read_report(record.run_id) or ""
    assert f"`{record.run_id}`" in report, report[:200]
    assert store.read_summary(record.run_id)["run_id"] == record.run_id

    # 事件流里也不能出现第二个 id，否则前端按 id 过滤会丢事件
    assert all(e.seq > 0 for e in bus.history(record.run_id))


async def test_runner_folds_token_usage_from_the_client(tmp_path: Path, demo_repo, defects):
    """token 用量必须进入结果——否则"成本"这一维度永远是 0，固定预算实验也就无法解释。"""
    store = RunStore(tmp_path / "runs")
    bus = RunEventBus()
    usage = UsageStats(calls=777, prompt_tokens=1234, completion_tokens=567)
    client = FakeLLMClient(make_responder(defects), usage=usage)

    runner = AuditRunner(store, bus, make_settings(max_rounds=1), client_factory=lambda _s: client)
    record = runner.submit(repo_path=str(demo_repo), overrides={})
    await runner.shutdown()

    summary = store.read_summary(record.run_id)
    assert summary["usage"]["prompt_tokens"] == 1234
    assert summary["usage"]["completion_tokens"] == 567
    assert summary["usage"]["calls"] > 0

    # 两本账必须保持分开：calls 是"Reader 调用次数"（编排层统计），
    # 不能变成客户端那条按 HTTP 请求计的计数——否则已发布的对比实验数字会整体翻倍。
    # 客户端被预置成 777 次，若两本账被合成一本，这里的值也会变成 780。
    assert summary["usage"]["calls"] < usage.calls


async def test_runner_records_failures_instead_of_raising(tmp_path: Path, demo_repo):
    """任何失败都必须落到运行记录里——否则前端只会看到流断了却不知为何。"""
    store = RunStore(tmp_path / "runs")
    bus = RunEventBus()

    def boom(_settings):
        raise RuntimeError("客户端构造失败")

    runner = AuditRunner(store, bus, make_settings(), client_factory=boom)
    record = runner.submit(repo_path=str(demo_repo), overrides={})
    await runner.shutdown()

    saved = store.get(record.run_id)
    assert saved.status == "failed"
    assert "客户端构造失败" in (saved.error or "")
    assert any(e.type == "failed" for e in bus.history(record.run_id))
    assert bus.is_closed(record.run_id)


async def test_runner_recovers_queued_record_after_restart(tmp_path: Path, demo_repo, defects):
    """进程重启后，已落盘的 queued 任务应重新执行而不是永久卡住。"""
    store = RunStore(tmp_path / "runs")
    first = AuditRunner(
        store, RunEventBus(store.root), make_settings(), client_factory=lambda _s: None
    )
    record = first.submit(repo_path=str(demo_repo), overrides={})
    # 模拟进程在 task 启动前退出：只保留 queued 记录，不等待旧 runner。
    task = first._tasks.pop(record.run_id)  # noqa: SLF001
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    store.update(record.run_id, status="queued")

    bus = RunEventBus(store.root)
    restarted = AuditRunner(
        store,
        bus,
        make_settings(max_rounds=1),
        client_factory=lambda _s: FakeLLMClient(make_responder(defects)),
    )
    assert restarted.recover() == 1
    await restarted.shutdown()
    assert store.get(record.run_id).status == "done"
    assert any(event.type == "recovered" for event in bus.history(record.run_id))


async def test_runner_cancel_has_terminal_state(tmp_path: Path, demo_repo):
    store = RunStore(tmp_path / "runs")
    runner = AuditRunner(
        store, RunEventBus(store.root), make_settings(), client_factory=lambda _s: None
    )
    record = runner.submit(repo_path=str(demo_repo), overrides={})
    assert runner.cancel(record.run_id) is not None
    await runner.shutdown()
    saved = store.get(record.run_id)
    assert saved.status == "canceled"
    assert any(event.type == "canceled" for event in runner.bus.history(record.run_id))


def test_runner_rejects_missing_repo(tmp_path: Path):
    from parallax.domain.errors import ConfigurationError

    runner = AuditRunner(
        RunStore(tmp_path / "runs"), RunEventBus(), make_settings(), client_factory=lambda _s: None
    )
    with pytest.raises(ConfigurationError):
        runner.submit(repo_path=str(tmp_path / "nope"), overrides={})


def test_runner_enforces_audit_root(tmp_path: Path, demo_repo):
    from parallax.domain.errors import ConfigurationError

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    runner = AuditRunner(
        RunStore(tmp_path / "runs"),
        RunEventBus(),
        make_settings(audit_root=str(allowed)),
        client_factory=lambda _s: None,
    )
    with pytest.raises(ConfigurationError, match="允许的审查根目录"):
        runner.submit(repo_path=str(demo_repo), overrides={})


def test_runner_settings_whitelist(tmp_path: Path):
    """只认白名单键，防止远程请求改写任意框架配置。"""
    runner = AuditRunner(
        RunStore(tmp_path / "runs"), RunEventBus(), make_settings(), client_factory=lambda _s: None
    )
    merged = runner._merge_settings(  # noqa: SLF001
        {"readers": 5, "visibility": "shared", "llm_api_key": "HACKED", "runs_dir": "/tmp/evil"}
    )
    assert merged.n_readers == 5
    assert merged.reader_visibility == "shared"
    assert merged.llm_api_key != "HACKED"
    assert str(merged.runs_dir) != "/tmp/evil"

    advanced = runner._merge_settings(  # noqa: SLF001
        {"enable_llm_falsifier": True, "adaptive_scheduling": True}
    )
    assert advanced.enable_llm_falsifier is True
    assert advanced.adaptive_scheduling is True


# ──────────────────────────── HTTP ────────────────────────────


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(
        make_settings(),
        runs_dir=tmp_path / "runs",
        client_factory=lambda _s: FakeLLMClient(responder=lambda _m: {"findings": []}),
    )
    with TestClient(app) as c:
        yield c


def test_health_and_ready_endpoints(client: TestClient):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["llm_configured"] is False  # 测试夹具强制清空了凭据

    ready = client.get("/ready").json()
    assert ready["ready"] is False
    assert any("OPENAI_API_KEY" in r for r in ready["reasons"])


def test_meta_lists_plugins_and_defaults(client: TestClient):
    meta = client.get("/api/v1/meta").json()
    assert meta["defaults"]["readers"] >= 1
    assert meta["plugins"][0]["name"] == "code_audit"
    assert "concurrency" in meta["plugins"][0]["defect_classes"]
    assert "adaptive_scheduling" in meta["defaults"]
    assert "enable_llm_falsifier" in meta["defaults"]


def test_submit_rejects_bad_path(client: TestClient, tmp_path: Path):
    response = client.post("/api/v1/audits", json={"repo_path": str(tmp_path / "nope")})
    assert response.status_code == 400
    assert "不存在" in response.json()["detail"]


def test_submit_returns_urls(client: TestClient, demo_repo):
    response = client.post(
        "/api/v1/audits",
        json={"repo_path": str(demo_repo), "readers": 2, "max_rounds": 1},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["run_id"]
    assert body["events_url"].endswith("/events")
    assert body["result_url"].endswith("/result")

    listed = client.get("/api/v1/audits").json()
    assert listed["total"] == 1
    assert listed["runs"][0]["run_id"] == body["run_id"]


def test_unknown_run_returns_404(client: TestClient):
    assert client.get("/api/v1/audits/nope").status_code == 404
    assert client.get("/api/v1/audits/nope/result").status_code == 404
    assert client.get("/api/v1/audits/nope/events").status_code == 404


def test_cancel_endpoint_is_idempotent(client: TestClient, demo_repo):
    run_id = client.post("/api/v1/audits", json={"repo_path": str(demo_repo)}).json()["run_id"]
    response = client.delete(f"/api/v1/audits/{run_id}")
    assert response.status_code == 200
    assert response.json()["run_id"] == run_id


def test_github_webhook_requires_signature(tmp_path: Path):
    app = create_app(
        make_settings(webhook_secret="secret"),
        runs_dir=tmp_path / "runs",
        client_factory=lambda _s: FakeLLMClient(responder=lambda _m: {"findings": []}),
    )
    with TestClient(app) as c:
        payload = b'{"action":"opened"}'
        assert c.post("/api/v1/webhooks/github", content=payload).status_code == 401
        signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
        assert (
            c.post(
                "/api/v1/webhooks/github",
                content=payload,
                headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "closed"},
            ).json()["accepted"]
            is False
        )


def test_result_is_pending_until_ready(client: TestClient, demo_repo):
    """结果未生成不是错误——前端应继续看事件流，而不是把它当失败。"""
    run_id = client.post("/api/v1/audits", json={"repo_path": str(demo_repo)}).json()["run_id"]
    body = client.get(f"/api/v1/audits/{run_id}/result").json()
    assert body["ready"] in (False, True)
    if not body["ready"]:
        assert body["status"] in ("queued", "running")


def test_sse_replays_history_for_a_closed_run(client: TestClient, demo_repo):
    run_id = client.post("/api/v1/audits", json={"repo_path": str(demo_repo)}).json()["run_id"]
    bus = client.app.state.bus
    bus.publish(run_id, "custom", {"n": 1})
    bus.publish(run_id, "custom", {"n": 2})
    bus.close(run_id)

    response = client.get(f"/api/v1/audits/{run_id}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: custom" in body
    assert '"n": 2' in body


def test_sse_honours_replay_cursor(client: TestClient, demo_repo):
    run_id = client.post("/api/v1/audits", json={"repo_path": str(demo_repo)}).json()["run_id"]
    bus = client.app.state.bus
    first = bus.publish(run_id, "custom", {"n": 1})
    bus.publish(run_id, "custom", {"n": 2})
    bus.close(run_id)

    body = client.get(f"/api/v1/audits/{run_id}/events?after={first.seq}").text
    assert '"n": 2' in body
    assert '"n": 1' not in body


def test_report_404_before_generation(client: TestClient, demo_repo):
    run_id = client.post("/api/v1/audits", json={"repo_path": str(demo_repo)}).json()["run_id"]
    assert client.get(f"/api/v1/audits/{run_id}/report").status_code in (200, 404)
