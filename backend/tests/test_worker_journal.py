from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from parallax.service.worker_journal import JournalConflict, WorkerJournal
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
        deadline=datetime.now(UTC) + timedelta(hours=1),
    )


def test_concurrent_registration_and_launch_have_one_winner(tmp_path):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: journal.register(contract), range(20))) == 1
        assert sum(pool.map(lambda _: journal.claim_launch(contract), range(20))) == 1
    assert journal.unclaimed() == []
    restarted = WorkerJournal(journal.path)
    assert not restarted.claim_launch(contract)
    assert not restarted.register(contract)


def test_cancel_before_dispatch_does_not_lose_the_execution(tmp_path):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    journal.request_cancel(contract)
    assert journal.canceled(contract)
    assert not journal.register(contract)
    assert journal.unclaimed() == [contract]
    assert journal.claim_launch(contract)


def test_pending_event_survives_restart_and_reuses_exact_identity(tmp_path):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    journal.register(contract)
    journal.claim_launch(contract)
    event = journal.prepare(contract, "STARTED", 0, 0)
    restarted = WorkerJournal(journal.path)
    assert restarted.pending() == [event]
    assert restarted.prepare(contract, "STARTED", 0, 0) == event
    with pytest.raises(JournalConflict, match="earlier event"):
        restarted.prepare(contract, "PROGRESS", 1, 0)
    restarted.acknowledge(event)
    restarted.acknowledge(event)
    assert restarted.pending() == []
    progress = restarted.prepare(contract, "PROGRESS", 10, 5)
    assert progress.sequence == 2
    with pytest.raises(JournalConflict, match="differs"):
        restarted.acknowledge(progress.model_copy(update={"completion_tokens": 6}))
    restarted.acknowledge(progress)
    assert restarted.pending() == []


def test_terminal_retries_do_not_reopen_execution(tmp_path):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    journal.register(contract)
    journal.claim_launch(contract)
    journal.acknowledge(journal.prepare(contract, "STARTED", 0, 0))
    done = journal.prepare(contract, "SUCCEEDED", 20, 5, "b" * 64)
    assert journal.prepare(contract, "SUCCEEDED", 20, 5, "b" * 64) == done
    journal.acknowledge(done)
    with pytest.raises(JournalConflict, match="not active"):
        journal.prepare(contract, "PROGRESS", 20, 5)
    assert not journal.claim_launch(contract)


@pytest.mark.parametrize(
    "change", [{"fencing_token": 2}, {"repository_id": "other"}, {"token_budget": 99}]
)
def test_contract_cannot_change_within_an_attempt(tmp_path, change):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    journal.register(contract)
    with pytest.raises(JournalConflict, match="changed"):
        journal.register(contract.model_copy(update=change))
    with pytest.raises(JournalConflict):
        journal.claim_launch(contract.model_copy(update=change))


def test_usage_and_initial_grant_invariants(tmp_path):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    journal.register(contract)
    with pytest.raises(JournalConflict, match="not active"):
        journal.prepare(contract, "STARTED", 0, 0)
    journal.claim_launch(contract)
    with pytest.raises(JournalConflict, match="zero-usage"):
        journal.prepare(contract, "PROGRESS", 1, 0)
    journal.acknowledge(journal.prepare(contract, "STARTED", 0, 0))
    journal.acknowledge(journal.prepare(contract, "PROGRESS", 10, 5))
    for prompt, completion in [(9, 5), (10, 4), (100, 1)]:
        with pytest.raises(JournalConflict, match="Usage"):
            journal.prepare(contract, "PROGRESS", prompt, completion)
    assert journal.pending() == []


def test_pending_batches_are_bounded_and_attempts_are_separate(tmp_path):
    journal = WorkerJournal(tmp_path / "worker.db")
    contract = task()
    other = contract.model_copy(update={"attempt": 2, "fencing_token": 2})
    for current in [contract, other]:
        journal.register(current)
        journal.claim_launch(current)
        journal.prepare(current, "STARTED", 0, 0)
    assert len(journal.pending(1)) == 1
    assert len(journal.pending()) == 2
    for limit in [0, 101]:
        with pytest.raises(ValueError):
            journal.pending(limit)
        with pytest.raises(ValueError):
            journal.unclaimed(limit)
