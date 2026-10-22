import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from parallax.config import Settings
from parallax.service.platform_client import PlatformRejected, PlatformUnavailable
from parallax.service.platform_worker import PlatformWorkerService
from parallax.service.worker_protocol import WorkerTask


def task():
    return WorkerTask(
        schema_version=1,
        task_id="task",
        attempt=1,
        fencing_token=1,
        organization_id="org",
        project_id="project",
        repository_id="repo",
        commit_sha="a" * 40,
        policy_version="policy",
        token_budget=100,
        deadline=datetime.now(UTC) + timedelta(minutes=10),
    )


class Client:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.events = []
        self.closed = 0

    async def snapshot(self, value):
        policy = type(
            "Policy",
            (),
            {
                "readers": 2,
                "redundancy": 1,
                "maxRounds": 1,
                "minIndependentSupport": 1,
                "falsifierEnabled": False,
                "maxTokenBudget": 100,
                "deadlineSeconds": 600,
            },
        )()
        return type("Snapshot", (), {"policy": lambda _: policy, "cancel_requested": False})()

    async def send(self, event):
        self.events.append(event)
        if self.fail:
            raise PlatformUnavailable("offline")
        return {"accepted": True}

    async def upload_artifact(self, *args):
        return {"artifact_id": args[1], "sha256": args[2]}

    async def aclose(self):
        self.closed += 1


@pytest.mark.asyncio
async def test_dispatch_claims_once_and_does_not_duplicate_engine(tmp_path: Path):
    clients = []
    started = []

    def make_client(_):
        value = Client()
        clients.append(value)
        return value

    async def engine(**kwargs):
        started.append(kwargs["task"].task_id)
        return "{}", 2, 3, "a" * 64

    service = PlatformWorkerService(
        Settings(
            platform_url="http://platform",
            gateway_internal_token="token",
            platform_source_hosts=["github.com"],
        ),
        tmp_path,
        client_factory=make_client,
        engine_factory=engine,
    )
    contract = task()
    assert await service.dispatch(contract) == "started"
    running = service._running[("task", 1)]
    assert await service.dispatch(contract) == "duplicate"
    await running
    assert started == ["task"]
    assert [event.kind for event in clients[0].events] == ["STARTED", "SUCCEEDED"]


@pytest.mark.asyncio
async def test_failed_ack_is_persisted_for_exact_replay(tmp_path: Path):
    clients = []

    def make_client(_):
        value = Client(fail=True)
        clients.append(value)
        return value

    async def engine(**kwargs):
        raise AssertionError("engine must not start without STARTED acknowledgement")

    service = PlatformWorkerService(
        Settings(
            platform_url="http://platform",
            gateway_internal_token="token",
            platform_source_hosts=["github.com"],
        ),
        tmp_path,
        client_factory=make_client,
        engine_factory=engine,
    )
    with pytest.raises(PlatformUnavailable):
        await service.dispatch(task())
    pending = service.journal.pending()
    assert [event.kind for event in pending] == ["STARTED"]
    assert await service.replay() == 0


def worker(tmp_path, client, engine):
    return PlatformWorkerService(
        Settings(
            platform_url="http://platform",
            gateway_internal_token="token",
            platform_source_hosts=["github.com"],
            platform_heartbeat_seconds=0.01,
            platform_replay_seconds=0.01,
        ),
        tmp_path,
        client_factory=lambda _: client,
        engine_factory=engine,
    )


async def test_long_execution_renews_lease_before_success(tmp_path):
    renewed = asyncio.Event()

    class HeartbeatClient(Client):
        async def send(self, event):
            response = await super().send(event)
            if event.kind == "PROGRESS":
                renewed.set()
            return response

    client = HeartbeatClient()

    async def engine(**kwargs):
        await renewed.wait()
        return "{}", 2, 3, "a" * 64

    service = worker(tmp_path, client, engine)
    await service.dispatch(task())
    await asyncio.wait_for(service._running[("task", 1)], 2)
    assert [event.kind for event in client.events] == ["STARTED", "PROGRESS", "SUCCEEDED"]
    assert [event.sequence for event in client.events] == [1, 2, 3]
    assert client.closed == 1


@pytest.mark.parametrize("failure", [PlatformUnavailable, PlatformRejected])
async def test_heartbeat_failure_stops_engine_and_never_refunds_unknown_usage(tmp_path, failure):
    stopped = asyncio.Event()

    class OfflineClient(Client):
        async def send(self, event):
            if event.kind == "PROGRESS":
                self.events.append(event)
                raise failure("lost contact")
            return await super().send(event)

    async def engine(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client = OfflineClient()
    service = worker(tmp_path, client, engine)
    await service.dispatch(task())
    await asyncio.wait_for(service._running[("task", 1)], 2)
    assert stopped.is_set()
    assert [event.kind for event in client.events] == ["STARTED", "PROGRESS"]
    assert service.journal.pending()[0] == client.events[-1]
    assert client.closed == 1


async def test_authoritative_cancel_stops_engine_without_zero_usage_terminal(tmp_path):
    stopped = asyncio.Event()

    class CancelingClient(Client):
        async def send(self, event):
            await super().send(event)
            return {"accepted": True, "cancelRequested": event.kind == "PROGRESS"}

    async def engine(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client = CancelingClient()
    service = worker(tmp_path, client, engine)
    contract = task()
    await service.dispatch(contract)
    await asyncio.wait_for(service._running[("task", 1)], 2)
    assert stopped.is_set()
    assert service.journal.canceled(contract)
    assert [event.kind for event in client.events] == ["STARTED", "PROGRESS"]


async def test_deadline_cancels_engine_even_when_no_progress_arrives(tmp_path):
    stopped = asyncio.Event()

    async def engine(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client = Client()
    service = worker(tmp_path, client, engine)
    contract = task().model_copy(update={"deadline": datetime.now(UTC) + timedelta(seconds=0.2)})
    await service.dispatch(contract)
    await asyncio.wait_for(service._running[("task", 1)], 2)
    assert stopped.is_set()
    assert all(event.kind in {"STARTED", "PROGRESS"} for event in client.events)
    assert client.closed == 1


async def test_restart_replays_exact_receipt_without_launching_engine(tmp_path):
    online = asyncio.Event()
    client = Client(fail=True)

    async def engine(**kwargs):
        raise AssertionError("restart must not relaunch claimed model work")

    service = worker(tmp_path, client, engine)
    contract = task()
    with pytest.raises(PlatformUnavailable):
        await service.dispatch(contract)
    original = service.journal.pending()[0]

    class OnlineClient(Client):
        async def send(self, event):
            result = await super().send(event)
            online.set()
            return result

    restarted_client = OnlineClient()
    restarted = worker(tmp_path, restarted_client, engine)
    await restarted.start()
    try:
        await asyncio.wait_for(online.wait(), 2)
        assert restarted.journal.pending() == []
        assert restarted_client.events == [original]
        assert await restarted.dispatch(contract) == "duplicate"
    finally:
        await restarted.shutdown()


async def test_shutdown_cancels_inflight_work_and_rejects_new_dispatch(tmp_path):
    started, stopped = asyncio.Event(), asyncio.Event()

    async def engine(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client = Client()
    service = worker(tmp_path, client, engine)
    await service.start()
    await service.dispatch(task())
    await asyncio.wait_for(started.wait(), 2)
    await asyncio.wait_for(service.shutdown(), 2)
    assert stopped.is_set()
    assert [event.kind for event in client.events] == ["STARTED"]
    assert client.closed == 1
    with pytest.raises(PlatformUnavailable, match="shutting down"):
        await service.dispatch(task())


async def test_slow_replay_does_not_block_another_tasks_heartbeat(tmp_path):
    replay_started, release_replay, renewed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class SlowClient(Client):
        async def send(self, event):
            if event.task_id == "offline":
                replay_started.set()
                await release_replay.wait()
            if event.kind == "PROGRESS":
                renewed.set()
            return await super().send(event)

    async def engine(**kwargs):
        await renewed.wait()
        return "{}", 2, 3, "a" * 64

    service = worker(tmp_path, SlowClient(), engine)
    offline = task().model_copy(update={"task_id": "offline"})
    service.journal.register(offline)
    service.journal.claim_launch(offline)
    service.journal.prepare(offline, "STARTED", 0, 0)
    replay = asyncio.create_task(service.replay())
    try:
        await asyncio.wait_for(replay_started.wait(), 2)
        await service.dispatch(task())
        await asyncio.wait_for(service._running[("task", 1)], 2)
        assert renewed.is_set()
        assert not replay.done()
    finally:
        release_replay.set()
        await asyncio.wait_for(replay, 2)
        await service.shutdown()


async def test_cancel_in_started_ack_prevents_engine_launch(tmp_path):
    class CancelingClient(Client):
        async def send(self, event):
            await super().send(event)
            return {"accepted": True, "cancelRequested": True}

    async def engine(**kwargs):
        raise AssertionError("a canceled execution grant must not start model work")

    client = CancelingClient()
    service = worker(tmp_path, client, engine)
    assert await service.dispatch(task()) == "canceled"
    assert [event.kind for event in client.events] == ["STARTED", "CANCELED"]
    assert not service._running


async def test_shutdown_while_claim_pending_prevents_late_engine_launch(tmp_path):
    grant_started, release_grant = asyncio.Event(), asyncio.Event()

    class DelayedClient(Client):
        async def send(self, event):
            grant_started.set()
            await release_grant.wait()
            return await super().send(event)

    async def engine(**kwargs):
        raise AssertionError("shutdown must prevent late engine launch")

    service = worker(tmp_path, DelayedClient(), engine)
    dispatch = asyncio.create_task(service.dispatch(task()))
    try:
        await asyncio.wait_for(grant_started.wait(), 2)
        await service.shutdown()
    finally:
        release_grant.set()
    with pytest.raises(PlatformUnavailable, match="shutting down"):
        await dispatch
    assert not service._running


@pytest.mark.asyncio
async def test_platform_execution_concurrency_is_bounded(tmp_path):
    active = peak = 0
    first_started = asyncio.Event()
    release = asyncio.Event()

    async def engine(**kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        first_started.set()
        await release.wait()
        active -= 1
        return "{}", 0, 0, "a" * 64

    service = PlatformWorkerService(
        Settings(
            platform_url="http://platform",
            gateway_internal_token="token",
            platform_source_hosts=["github.com"],
            platform_max_concurrent_tasks=1,
        ),
        tmp_path,
        client_factory=lambda _: Client(),
        engine_factory=engine,
    )
    first = task().model_copy(update={"task_id": "first"})
    second = task().model_copy(update={"task_id": "second"})
    assert await service.dispatch(first) == "started"
    await asyncio.wait_for(first_started.wait(), 2)
    assert await service.dispatch(second) == "started"
    await asyncio.sleep(0.1)
    assert peak == 1

    running = list(service._running.values())
    release.set()
    await asyncio.gather(*running, return_exceptions=True)
    assert peak == 1
