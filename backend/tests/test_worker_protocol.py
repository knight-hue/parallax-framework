from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from parallax.service.worker_protocol import TaskState, WorkerEvent, WorkerTask

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "worker" / "v1"


def task_payload():
    return WorkerTask.model_validate_json((FIXTURES / "task.json").read_text()).model_dump()


def event_payload():
    return WorkerEvent.model_validate_json((FIXTURES / "succeeded.json").read_text()).model_dump()


def test_shared_java_python_fixtures_and_deadline():
    task = WorkerTask(**task_payload())
    event = WorkerEvent(**event_payload())
    event.require_current(task)
    assert event.prompt_tokens + event.completion_tokens == 120
    task.require_active(datetime(2026, 10, 20, tzinfo=UTC))
    with pytest.raises(ValueError, match="deadline"):
        task.require_active(task.deadline)


@pytest.mark.parametrize("attempt", [0, 2.5, "2", None, True, 2**31])
def test_rejects_invalid_attempts(attempt):
    payload = task_payload() | {"attempt": attempt}
    with pytest.raises(ValidationError):
        WorkerTask(**payload)


@pytest.mark.parametrize("updates", [{"attempt": 1}, {"fencing_token": 6}, {"task_id": "other"}])
def test_old_attempt_or_fence_cannot_complete_new_execution(updates):
    event = WorkerEvent(**(event_payload() | updates))
    with pytest.raises(ValueError, match="Stale"):
        event.require_current(WorkerTask(**task_payload()))


@pytest.mark.parametrize(
    "updates",
    [
        {"api_key": "forbidden"},
        {"schema_version": 2},
        {"commit_sha": "HEAD"},
        {"deadline": "2030-01-01T00:00:00"},
        {"project_id": "../other-project"},
        {"token_budget": 2**63},
    ],
)
def test_rejects_unknown_or_unpinned_inputs(updates):
    with pytest.raises(ValidationError):
        WorkerTask(**(task_payload() | updates))


@pytest.mark.parametrize(
    "updates",
    [
        {"kind": "PROGRESS"},
        {"kind": 2},
        {"result_sha256": None},
        {"result_sha256": "invalid"},
        {"prompt_tokens": 2**63 - 1},
    ],
)
def test_event_result_and_usage_invariants(updates):
    with pytest.raises(ValidationError):
        WorkerEvent(**(event_payload() | updates))


def test_lifecycle_handles_cancel_race_without_reopening_terminal():
    state = TaskState.QUEUED.transition_to(TaskState.DISPATCHED)
    state = state.transition_to(TaskState.RUNNING).transition_to(TaskState.CANCEL_REQUESTED)
    assert state.transition_to(TaskState.SUCCEEDED) == TaskState.SUCCEEDED
    assert state.transition_to(TaskState.CANCELED) == TaskState.CANCELED
    assert TaskState.RUNNING.transition_to(TaskState.QUEUED) == TaskState.QUEUED
    for terminal in [TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELED]:
        assert terminal.transition_to(terminal) == terminal
        with pytest.raises(ValueError):
            terminal.transition_to(TaskState.RUNNING)
    with pytest.raises(ValueError):
        TaskState.QUEUED.transition_to(TaskState.SUCCEEDED)
