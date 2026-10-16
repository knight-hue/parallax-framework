"""账本与聚合器测试——机制 2 与机制 3 的核心行为。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from parallax.core.aggregator import AggregationRules, Aggregator
from parallax.core.ledger import ClaimLedger
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import Claim, SourceRef
from parallax.ports.claim_validator import ValidationResult
from tests.conftest import make_unit


def claim(
    fingerprint: str = "a.py#logic@0",
    agent: str = "reader-1",
    polarity: int = 1,
    reputation: float = 0.5,
    claim_type: str = "logic",
    claim_id: str | None = None,
) -> Claim:
    return Claim(
        claim_id=claim_id or f"{fingerprint}|{agent}|{polarity}",
        fingerprint=fingerprint,
        statement=f"{fingerprint} by {agent}",
        polarity=polarity,  # type: ignore[arg-type]
        claim_type=claim_type,
        extracted_by=agent,
        reputation_at_extraction=reputation,
        source_refs=[SourceRef(evidence_id="e1", adapter="test", locator="a.py:1-5")],
    )


# ---- 账本 ----


def test_claim_requires_source_ref():
    # 无源指针的 claim 必须被 pydantic 拦下，而不是进账本后才发现无法追溯
    with pytest.raises(ValidationError):
        Claim(
            claim_id="x",
            fingerprint="f",
            statement="s",
            extracted_by="a",
            source_refs=[],
        )


def test_ledger_grouping_counts_distinct_agents():
    ledger = ClaimLedger()
    shard = [make_unit("a.py", "x", "mod")]
    ledger.admit(claim(agent="r1"), shard)
    ledger.admit(claim(agent="r2"), shard)
    # 同一个 Agent 重复主张不应增加交叉验证数（那是自证）
    ledger.admit(claim(agent="r1", claim_id="dup"), shard)

    groups = ledger.groups()
    assert len(groups) == 1
    assert groups[0].cross_validation_count == 2
    assert groups[0].asserting_agents == ["r1", "r2"]


def test_ledger_rejects_are_recorded_not_swallowed():
    class RejectAll:
        name = "reject-all"

        def validate(self, c, shard):  # noqa: ANN001
            return ValidationResult.reject("nope", self.name)

    ledger = ClaimLedger(validators=[RejectAll()])
    assert ledger.admit(claim(), [make_unit("a.py", "x", "mod")]) is None
    assert len(ledger) == 0
    assert ledger.rejections[0].reason == "nope"
    assert ledger.rejections[0].validator == "reject-all"


# ---- 聚合 ----


def build(*claims) -> tuple[ClaimLedger, Aggregator]:
    ledger = ClaimLedger()
    shard = [make_unit("a.py", "x", "mod")]
    for c in claims:
        ledger.admit(c, shard)
    aggregator = Aggregator(ledger, AggregationRules(support_threshold=2))
    return ledger, aggregator


def test_single_source_is_pending():
    _, aggregator = build(claim(agent="r1"))
    groups = aggregator.sweep()
    assert groups[0].status == ClaimStatus.PENDING


def test_two_independent_agents_give_high_confidence():
    _, aggregator = build(claim(agent="r1"), claim(agent="r2"))
    groups = aggregator.sweep()
    assert groups[0].status == ClaimStatus.HIGH_CONFIDENCE
    assert groups[0].cross_validation_count == 2


def test_same_agent_twice_is_still_pending():
    """最关键的正确性断言：没有它，「多个 Agent」退化成「同一个 Agent 说两遍」。"""
    _, aggregator = build(claim(agent="r1"), claim(agent="r1", claim_id="again"))
    groups = aggregator.sweep()
    assert groups[0].status == ClaimStatus.PENDING


def test_opposite_polarity_triggers_dispute():
    ledger, aggregator = build(claim(agent="r1", polarity=1), claim(agent="r2", polarity=-1))
    groups = aggregator.sweep()
    assert groups[0].status == ClaimStatus.DISPUTED

    # 争议双方互相记录为 dispute 对手
    first = ledger.claim("a.py#logic@0|r1|1")
    second = ledger.claim("a.py#logic@0|r2|-1")
    assert second.claim_id in first.disputed_with
    assert first.claim_id in second.disputed_with
    assert len(aggregator.arbitration_queue(groups)) == 1


def test_confidence_is_neutral_for_two_average_agents():
    """声誉 0.5 的 Agent 贡献 0 权重——两个平庸 Agent 不构成任何证据。"""
    _, aggregator = build(claim(agent="r1"), claim(agent="r2"))
    groups = aggregator.sweep()
    assert groups[0].status == ClaimStatus.HIGH_CONFIDENCE
    assert abs(aggregator.confidence(groups[0]) - 0.5) < 1e-9


def test_confidence_rises_with_reputation():
    _, aggregator = build(claim(agent="r1", reputation=0.9), claim(agent="r2", reputation=0.9))
    groups = aggregator.sweep()
    assert aggregator.confidence(groups[0]) > 0.9


def test_dissent_lowers_confidence_symmetrically():
    _, two_yea = build(claim(agent="r1", reputation=0.9), claim(agent="r2", reputation=0.9))
    c_two = two_yea.confidence(two_yea.sweep()[0])

    _, two_yea_one_nay = build(
        claim(agent="r1", reputation=0.9),
        claim(agent="r2", reputation=0.9),
        claim(agent="r3", polarity=-1, reputation=0.9),
    )
    group = two_yea_one_nay.sweep()[0]
    c_with_dissent = two_yea_one_nay.confidence(group)

    assert group.status == ClaimStatus.DISPUTED
    # 三方声誉相同 → 反对票把证据权重从 logit*2 拉回 logit*1，置信度正好回落到单票水平
    assert c_with_dissent < c_two
    assert abs(c_with_dissent - 0.9) < 1e-6
    assert c_with_dissent > 0.5


def test_sweep_backfills_status_on_claims():
    ledger, aggregator = build(claim(agent="r1"), claim(agent="r2"))
    aggregator.sweep()
    assert all(c.status == ClaimStatus.HIGH_CONFIDENCE for c in ledger.claims)
    assert ledger.claims[0].verified_by == ["r1", "r2"]


def test_arbitration_clears_dispute():
    _, aggregator = build(claim(agent="r1", polarity=1), claim(agent="r2", polarity=-1))
    groups = aggregator.sweep()
    aggregator.apply_arbitration(groups[0], ClaimStatus.HIGH_CONFIDENCE)
    assert aggregator.sweep()[0].status == ClaimStatus.HIGH_CONFIDENCE


def test_polarity_enum_values():
    assert Polarity.ASSERT == 1
    assert Polarity.DENY == -1
