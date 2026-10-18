"""持久化声誉存储测试。"""

from pathlib import Path

from parallax.core.reputation import SQLiteReputationStore
from parallax.domain.models import AgentReputation


def test_sqlite_reputation_survives_a_new_store_instance(tmp_path: Path):
    path = tmp_path / "reputation.sqlite3"
    first = SQLiteReputationStore(path)
    reputation = first.get("reader-1")
    reputation.record("run-1", "claim-1", "verified")
    first.save(reputation)

    second = SQLiteReputationStore(path)
    restored = second.get("reader-1")
    assert restored.claims_verified == 1
    assert restored.score() == 2 / 3
    assert second.scores() == {"reader-1": round(2 / 3, 4)}


def test_sqlite_reputation_upsert_preserves_role_and_events(tmp_path: Path):
    store = SQLiteReputationStore(tmp_path / "reputation.sqlite3")
    store.save(AgentReputation(agent_id="arbiter-1", role="arbitrator"))
    loaded = store.get("arbiter-1")
    loaded.record("run-2", "claim-2", "arbitration_win")
    store.save(loaded)

    [item] = store.all()
    assert item.role == "arbitrator"
    assert item.arbitration_wins == 1
    assert item.events[0].outcome == "arbitration_win"
