from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from parallax.config import Settings
from parallax.service.platform_client import PlatformUnavailable
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
