import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from parallax.service.platform_client import PlatformClient, PlatformRejected, PlatformUnavailable
from parallax.service.worker_protocol import WorkerEvent, WorkerTask


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
        deadline=datetime.now(UTC) + timedelta(hours=1),
    )


def snapshot(contract):
    policy = json.dumps(
        {
            "readers": 4,
            "redundancy": 2,
            "maxRounds": 3,
            "minIndependentSupport": 2,
            "falsifierEnabled": True,
            "maxTokenBudget": 1000,
            "deadlineSeconds": 3600,
        }
    )
    return {
        "task": contract.model_dump(mode="json"),
        "clone_url": "https://github.com/team/api",
        "policy_json": policy,
        "policy_sha256": hashlib.sha256(policy.encode()).hexdigest(),
        "cancel_requested": False,
    }


def event(contract):
    return WorkerEvent(
        schema_version=1,
        event_id="event",
        task_id=contract.task_id,
        attempt=1,
        fencing_token=1,
        sequence=1,
        kind="STARTED",
        occurred_at=datetime.now(UTC),
        prompt_tokens=0,
        completion_tokens=0,
    )


def ack(receipt):
    return {
        "accepted": True,
        "cancelRequested": False,
        "task": {
            "id": receipt.task_id,
            "attempt": 1,
            "fencingToken": 1,
            "lastSequence": 1,
            "state": "RUNNING",
            "leaseUntil": (datetime.now(UTC) + timedelta(seconds=120)).isoformat(),
        },
    }


async def test_snapshot_and_grant_check_private_headers_and_fixed_paths():
    contract = task()
    receipt = event(contract)
    calls = []

    def handler(request):
        assert request.headers["X-Internal-Token"] == "secret"
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json=snapshot(contract)
            if request.url.path.endswith("execution-snapshot")
            else ack(receipt),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = PlatformClient("http://platform", "secret", client=http)
        assert (await client.snapshot(contract)).policy().readers == 4
        assert (await client.send(receipt))["accepted"]
        await client.aclose()
        assert not http.is_closed
    assert calls == [
        "/api/v1/internal/platform/execution-snapshot",
        "/api/v1/internal/platform/events",
    ]


@pytest.mark.parametrize(
    "status,exception",
    [
        (302, PlatformRejected),
        (401, PlatformRejected),
        (409, PlatformRejected),
        (410, PlatformRejected),
        (429, PlatformUnavailable),
        (503, PlatformUnavailable),
    ],
)
async def test_status_failures_never_grant_work(status, exception):
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(status, headers={"Location": "http://other-host/"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as http:
        client = PlatformClient("http://platform", "secret", client=http)
        with pytest.raises(exception):
            await client.snapshot(task())
    assert calls == ["platform"]


@pytest.mark.parametrize("change", ["hash", "task", "policy", "cancel"])
async def test_invalid_execution_snapshot_is_rejected(change):
    contract = task()
    body = snapshot(contract)
    if change == "hash":
        body["policy_sha256"] = "0" * 64
    if change == "task":
        body["task"]["token_budget"] = 101
    if change == "policy":
        body["policy_json"] = body["policy_json"].replace('"readers": 4', '"readers": 1')
        body["policy_sha256"] = hashlib.sha256(body["policy_json"].encode()).hexdigest()
    if change == "cancel":
        body["cancel_requested"] = "false"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as http:
        with pytest.raises(PlatformRejected):
            await PlatformClient("http://platform", "secret", client=http).snapshot(contract)


@pytest.mark.parametrize("change", ["attempt", "sequence", "state", "lease", "types"])
async def test_invalid_or_expired_grants_are_rejected(change):
    receipt = event(task())
    body = ack(receipt)
    if change == "attempt":
        body["task"]["attempt"] = 2
    if change == "sequence":
        body["task"]["lastSequence"] = 0
    if change == "state":
        body["task"]["state"] = "FAILED"
    if change == "lease":
        body["task"]["leaseUntil"] = datetime.now(UTC).isoformat()
    if change == "types":
        body["accepted"] = "true"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as http:
        with pytest.raises(PlatformRejected):
            await PlatformClient("http://platform", "secret", client=http).send(receipt)


async def test_network_and_unparseable_acknowledgements_are_retryable():
    for response in [httpx.Response(200, content=b"invalid"), httpx.Response(200, json=[])]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _, current=response: current)
        ) as http:
            with pytest.raises(PlatformUnavailable):
                await PlatformClient("http://platform", "secret", client=http).send(event(task()))

    def down(request):
        raise httpx.ConnectError("down", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(down)) as http:
        with pytest.raises(PlatformUnavailable):
            await PlatformClient("http://platform", "secret", client=http).snapshot(task())


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp",
        "http://user:password@host",
        "http://host/path",
        "http://host?query",
        "http://host/#fragment",
    ],
)
def test_only_a_fixed_origin_is_allowed(url):
    with pytest.raises(ValueError):
        PlatformClient(url, "secret")


@pytest.mark.parametrize(
    "change", [None, "taskId", "attempt", "fencingToken", "sha256", "content", "artifactId"]
)
async def test_artifact_acknowledgement_must_match_execution_and_content(change):
    contract = task()
    content = '{"report":"中文 😀"}'
    digest = hashlib.sha256(content.encode()).hexdigest()
    result = {
        "artifactId": "stored-artifact",
        "taskId": contract.task_id,
        "attempt": 1,
        "fencingToken": 1,
        "sha256": digest,
        "content": content,
    }
    if change is not None:
        result[change] = None

    def handler(request):
        assert request.url.path == "/api/v1/internal/platform/artifacts"
        assert request.headers["X-Internal-Token"] == "secret"
        assert json.loads(request.content)["content"] == content
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = PlatformClient("http://platform", "secret", client=http)
        if change is None:
            assert await client.upload_artifact(contract, "new-artifact", digest, content) == result
        else:
            with pytest.raises(PlatformRejected, match="artifact acknowledgement"):
                await client.upload_artifact(contract, "new-artifact", digest, content)
