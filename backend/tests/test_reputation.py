"""声誉更新策略测试——重点验证「异见者不受惩罚」。"""

from __future__ import annotations

from parallax.core.aggregator import AggregationRules, Aggregator
from parallax.core.ledger import ClaimLedger
from parallax.core.reputation import InMemoryReputationStore, ReputationPolicy
from parallax.domain.enums import ClaimStatus
from parallax.domain.models import Claim, SourceRef
from tests.conftest import make_unit


def claim(agent: str, polarity: int = 1, fingerprint: str = "a.py#logic@0") -> Claim:
    return Claim(
        claim_id=f"{fingerprint}|{agent}|{polarity}",
        fingerprint=fingerprint,
        statement="s",
        polarity=polarity,  # type: ignore[arg-type]
        claim_type="logic",
        extracted_by=agent,
        reputation_at_extraction=0.5,
        source_refs=[SourceRef(evidence_id="e1", adapter="t", locator="a.py:1")],
    )


def setup(*claims: Claim):
    ledger = ClaimLedger()
    shard = [make_unit("a.py", "x", "mod")]
    for c in claims:
        ledger.admit(c, shard)
    aggregator = Aggregator(ledger, AggregationRules(support_threshold=2))
    store = InMemoryReputationStore()
    policy = ReputationPolicy(store)
    return ledger, aggregator, store, policy


def test_neutral_start():
    store = InMemoryReputationStore()
    assert store.get("nobody").score() == 0.5


def test_cross_validated_agents_gain_reputation():
    ledger, aggregator, store, policy = setup(claim("r1"), claim("r2"))
    groups = aggregator.sweep()
    policy.apply_cross_validation(groups, ledger, "run-1")

    assert store.get("r1").claims_verified == 1
    assert store.get("r2").claims_verified == 1
    assert store.get("r1").score() > 0.5


def test_pending_claims_do_not_change_reputation():
    """孤证既未被验证也未被否证，不携带信息——不该动声誉。"""
    ledger, aggregator, store, policy = setup(claim("r1"))
    groups = aggregator.sweep()
    policy.apply_cross_validation(groups, ledger, "run-1")

    assert store.get("r1").claims_verified == 0
    assert store.get("r1").score() == 0.5


def test_dissenters_are_not_punished_while_disputed():
    """本项目最重要的一条反从众规则。

    多数实现会用「少数服从多数」扣少数方的声誉——但那会训练出
    「不要第一个说不同意见」的行为，正是我们要消灭的东西。
    """
    ledger, aggregator, store, policy = setup(claim("r1", 1), claim("r2", -1))
    groups = aggregator.sweep()
    assert groups[0].status == ClaimStatus.DISPUTED

    policy.apply_cross_validation(groups, ledger, "run-1")

    assert store.get("r2").claims_refuted == 0
    assert store.get("r2").score() == 0.5
    assert store.get("r1").score() == 0.5


def test_arbitration_is_what_moves_reputation_on_disputes():
    ledger, aggregator, store, policy = setup(claim("r1", 1), claim("r2", -1))
    groups = aggregator.sweep()

    policy.apply_arbitration(groups[0], ledger, "run-1", ClaimStatus.HIGH_CONFIDENCE)

    assert store.get("r1").arbitration_wins == 1
    assert store.get("r2").arbitration_losses == 1
    assert store.get("r1").score() > store.get("r2").score()


def test_reputation_accumulates_across_runs():
    ledger, aggregator, store, policy = setup(claim("r1"), claim("r2"))
    policy.apply_cross_validation(aggregator.sweep(), ledger, "run-1")
    first = store.get("r1").score()

    ledger2, aggregator2, _store2, _policy2 = setup(claim("r1"), claim("r3"))
    policy.apply_cross_validation(aggregator2.sweep(), ledger2, "run-2")

    assert store.get("r1").score() > first
    assert len(store.get("r1").events) == 2


def test_events_are_recorded_for_audit():
    ledger, aggregator, store, policy = setup(claim("r1"), claim("r2"))
    policy.apply_cross_validation(aggregator.sweep(), ledger, "run-1")
    event = store.get("r1").events[0]
    assert event.run_id == "run-1"
    assert event.outcome == "verified"
