"""Fixed-endpoint internal platform client. No redirects or best-effort grants."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from parallax.service.worker_protocol import WorkerEvent, WorkerTask


class PlatformUnavailable(RuntimeError):
    """Transient failure: retain the exact event and retry before any more work."""


class PlatformRejected(RuntimeError):
    """Permanent or stale execution: stop without launching/relaunching."""


class ExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    readers: int = Field(ge=2, le=16)
    redundancy: int = Field(ge=1)
    maxRounds: int = Field(ge=1, le=8)
    minIndependentSupport: int = Field(ge=1)
    falsifierEnabled: bool
    maxTokenBudget: int = Field(ge=1, le=10_000_000)
    deadlineSeconds: int = Field(ge=60, le=86400)

    @model_validator(mode="after")
    def relationships(self):
        if self.redundancy > self.readers or self.minIndependentSupport > self.readers:
            raise ValueError("Policy support exceeds reader count")
        return self


class ExecutionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task: WorkerTask
    clone_url: str
    policy_json: str
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cancel_requested: StrictBool

    def policy(self) -> ExecutionPolicy:
        if hashlib.sha256(self.policy_json.encode()).hexdigest() != self.policy_sha256:
            raise ValueError("Policy integrity check failed")
        policy = ExecutionPolicy.model_validate_json(self.policy_json)
        if self.task.token_budget > policy.maxTokenBudget:
            raise ValueError("Task exceeds immutable policy budget")
        return policy


class PlatformClient:
    def __init__(self, base_url: str, token: str, *, client: httpx.AsyncClient | None = None):
        url = urlsplit(base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or not token.strip()
        ):
            raise ValueError("A fixed platform origin and internal credential are required")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._client = client or httpx.AsyncClient(
            timeout=5, follow_redirects=False, trust_env=False
        )
        self._owns_client = client is None

    async def aclose(self):
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, path: str, payload: str) -> dict:
        try:
            response = await self._client.post(
                self.base_url + path,
                content=payload,
                headers={"X-Internal-Token": self._token, "Content-Type": "application/json"},
                follow_redirects=False,
                timeout=5,
            )
        except httpx.TransportError as exc:
            raise PlatformUnavailable("Platform request failed") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise PlatformUnavailable(f"Platform HTTP {response.status_code}")
        if response.status_code != 200:
            raise PlatformRejected(f"Platform HTTP {response.status_code}")
        try:
            body = response.json()
        except (ValueError, UnicodeError) as exc:
            raise PlatformUnavailable("Invalid platform acknowledgement") from exc
        if not isinstance(body, dict):
            raise PlatformUnavailable("Invalid platform acknowledgement")
        return body

    async def snapshot(self, task: WorkerTask) -> ExecutionSnapshot:
        body = await self._post(
            "/api/v1/internal/platform/execution-snapshot", task.model_dump_json()
        )
        try:
            snapshot = ExecutionSnapshot.model_validate(body)
            if snapshot.task != task:
                raise ValueError("Execution contract differs")
            snapshot.policy()
        except ValueError as exc:
            raise PlatformRejected("Invalid execution snapshot") from exc
        return snapshot

    async def send(self, event: WorkerEvent) -> dict:
        body = await self._post("/api/v1/internal/platform/events", event.model_dump_json())
        try:
            accepted = body["accepted"]
            canceled = body["cancelRequested"]
            task = body["task"]
            if (
                type(accepted) is not bool
                or type(canceled) is not bool
                or not isinstance(task, dict)
            ):
                raise ValueError("Invalid acknowledgement types")
            if (
                task["id"] != event.task_id
                or task["attempt"] != event.attempt
                or task["fencingToken"] != event.fencing_token
                or task["lastSequence"] < event.sequence
            ):
                raise ValueError("Acknowledgement differs from the execution")
            # An idempotent STARTED replay after restart must not grant a new run
            # after terminal recovery, cancellation or lease expiry. The caller
            # must still hold its local one-time launch claim.
            if event.kind == "STARTED" and task["state"] not in {"RUNNING", "CANCEL_REQUESTED"}:
                raise ValueError("Execution grant is no longer active")
            if event.kind == "STARTED":
                lease = datetime.fromisoformat(task["leaseUntil"].replace("Z", "+00:00"))
                if lease.tzinfo is None or lease <= datetime.now(UTC):
                    raise ValueError("Execution grant lease expired")
        except (KeyError, TypeError, ValueError) as exc:
            raise PlatformRejected("Invalid execution acknowledgement") from exc
        return body

    async def upload_artifact(
        self, task: WorkerTask, artifact_id: str, sha256: str, content: str
    ) -> dict:
        body = {
            "task_id": task.task_id,
            "attempt": task.attempt,
            "fencing_token": task.fencing_token,
            "artifact_id": artifact_id,
            "sha256": sha256,
            "content": content,
        }
        result = await self._post(
            "/api/v1/internal/platform/artifacts", json.dumps(body, separators=(",", ":"))
        )
        if (
            result.get("taskId") != task.task_id
            or type(result.get("attempt")) is not int
            or result["attempt"] != task.attempt
            or type(result.get("fencingToken")) is not int
            or result["fencingToken"] != task.fencing_token
            or result.get("sha256") != sha256
            or result.get("content") != content
            or not isinstance(result.get("artifactId"), str)
            or not result["artifactId"]
        ):
            raise PlatformRejected("Invalid artifact acknowledgement")
        return result
