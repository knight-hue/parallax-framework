"""Versioned platform wire contracts; independent of the legacy file-based runner."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", strict=True)]
PositiveLong = Annotated[int, Field(strict=True, ge=1, le=2**63 - 1)]
PositiveAttempt = Annotated[int, Field(strict=True, ge=1, le=2**31 - 1)]
TokenCount = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, Field(strict=True)]

    @model_validator(mode="after")
    def supported_version(self):
        if self.schema_version != 1:
            raise ValueError("Unsupported schema version")
        return self


class WorkerTask(WireModel):
    task_id: Identifier
    attempt: PositiveAttempt
    fencing_token: PositiveLong
    organization_id: Identifier
    project_id: Identifier
    repository_id: Identifier
    commit_sha: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", strict=True)]
    policy_version: Identifier
    token_budget: PositiveLong
    deadline: AwareDatetime
    trace_id: Identifier | None = None

    def require_active(self, now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Clock must be timezone-aware")
        if self.deadline <= now:
            raise ValueError("Task deadline exceeded")


class WorkerEvent(WireModel):
    event_id: Identifier
    task_id: Identifier
    attempt: PositiveAttempt
    fencing_token: PositiveLong
    sequence: PositiveLong
    kind: Literal["STARTED", "PROGRESS", "SUCCEEDED", "FAILED", "CANCELED"]
    occurred_at: AwareDatetime
    result_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", strict=True)] | None = None
    prompt_tokens: TokenCount
    completion_tokens: TokenCount

    @model_validator(mode="after")
    def validate_result(self):
        if (self.kind == "SUCCEEDED") != (self.result_sha256 is not None):
            raise ValueError("Only successful events require result_sha256")
        if self.prompt_tokens + self.completion_tokens > 2**63 - 1:
            raise ValueError("Token total exceeds signed 64-bit range")
        return self

    def require_current(self, task: WorkerTask) -> None:
        if (self.task_id, self.attempt, self.fencing_token) != (
            task.task_id,
            task.attempt,
            task.fencing_token,
        ):
            raise ValueError("Stale or unrelated worker event")


class TaskState(StrEnum):
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

    def transition_to(self, next_state: TaskState) -> TaskState:
        transitions = {
            self.QUEUED: {self.DISPATCHED, self.CANCELED},
            self.DISPATCHED: {self.RUNNING, self.QUEUED, self.CANCEL_REQUESTED, self.FAILED},
            self.RUNNING: {self.QUEUED, self.CANCEL_REQUESTED, self.SUCCEEDED, self.FAILED},
            self.CANCEL_REQUESTED: {self.SUCCEEDED, self.FAILED, self.CANCELED},
            self.SUCCEEDED: set(),
            self.FAILED: set(),
            self.CANCELED: set(),
        }
        if next_state != self and next_state not in transitions[self]:
            raise ValueError(f"Invalid task transition: {self} -> {next_state}")
        return next_state
