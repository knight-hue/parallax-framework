"""独立性准入闸门的单元与端到端测试。

三件必须成立的事：
1. 阈值达标就放行，不打扰正常运行；
2. 阈值不达标时，enforce 会先尝试提高冗余重分区，用尽后降级为待验证；
3. observe 只报告不改变结论，off 连报告都不做——便于做对照实验。
"""

from __future__ import annotations

import pytest

from parallax.core.admission import IndependenceGate, blocked_fingerprints, suggest_remedy
from parallax.domain.enums import ClaimStatus
from parallax.domain.models import IndependenceProfile
from parallax.engine import ParallaxEngine
from parallax.infra.llm_fake import FakeLLMClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from tests.conftest import make_responder, make_settings


def _profile(
    *, effective: float = 2.0, normalized: float = 0.67, isolation: str = "verified"
) -> IndependenceProfile:
    return IndependenceProfile(
        reader_count=3,
        effective_channel_count=effective,
        normalized_independence=normalized,
        isolation_status=isolation,
    )


# ---- 纯判定 ----


def test_off_mode_never_blocks():
    gate = IndependenceGate(mode="off", min_effective_channels=3.0)
    decision = gate.evaluate(_profile(), attempts=0)
    assert decision.action == "accept"
    assert decision.blocking is False


def test_accepts_when_thresholds_are_met():
    gate = IndependenceGate(mode="enforce", min_effective_channels=2.5)
    decision = gate.evaluate(_profile(effective=2.8), attempts=0)
    assert decision.action == "accept"
    assert "达标" in decision.reason


def test_observe_reports_without_blocking():
    gate = IndependenceGate(mode="observe", min_effective_channels=3.0)
    decision = gate.evaluate(_profile(), attempts=0)
    assert decision.action == "observe"
    assert decision.blocking is False
    assert "observe" in decision.reason


def test_enforce_asks_for_repartition_before_downgrading():
    gate = IndependenceGate(mode="enforce", min_effective_channels=3.0, max_attempts=1)
    decision = gate.evaluate(_profile(), attempts=0)
    assert decision.action == "repartition"
    assert decision.blocking is True


def test_enforce_downgrades_after_attempts_exhausted():
    gate = IndependenceGate(mode="enforce", min_effective_channels=3.0, max_attempts=1)
    decision = gate.evaluate(_profile(), attempts=1)
    assert decision.action == "downgrade"
    assert "降级" in decision.reason


def test_output_contamination_is_never_fixed_by_repartition():
    gate = IndependenceGate(mode="enforce", min_effective_channels=0.0, max_attempts=3)
    decision = gate.evaluate(_profile(isolation="violated"), attempts=0)
    assert decision.action == "downgrade"
    assert "隔离" in decision.reason


def test_normalized_threshold_also_triggers():
    gate = IndependenceGate(mode="enforce", min_normalized_independence=0.9, max_attempts=0)
    decision = gate.evaluate(_profile(effective=3.0, normalized=0.5), attempts=0)
    assert decision.action == "downgrade"


def test_suggest_remedy_direction_matches_the_tradeoff():
    """重叠过高就降冗余；重叠不高就加 Reader；两者都不能动就不动。"""
    high_overlap = _profile(effective=1.0, normalized=0.33)
    high_overlap.evidence_overlap_rate = 0.9
    remedy, note = suggest_remedy(high_overlap, overlap_budget=0.5, n_readers=3, redundancy=3)
    assert remedy == "reduce_redundancy"
    assert "3 → 2" in note

    low_overlap = _profile(effective=2.0, normalized=0.67)
    low_overlap.evidence_overlap_rate = 0.1
    remedy, _ = suggest_remedy(low_overlap, overlap_budget=0.5, n_readers=3, redundancy=1)
    assert remedy == "add_reader"

    remedy, note = suggest_remedy(
        low_overlap, overlap_budget=0.5, n_readers=6, redundancy=1, max_readers=6
    )
    assert remedy == "none"
    assert "无法再提高" in note


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        IndependenceGate(mode="whatever")
    with pytest.raises(ValueError):
        IndependenceGate(mode="enforce", min_normalized_independence=1.5)
    with pytest.raises(ValueError):
        IndependenceGate(mode="enforce", min_effective_channels=-1)
    with pytest.raises(ValueError):
        IndependenceGate(mode="enforce", max_attempts=-1)


# ---- 降级副作用 ----


class _Group:
    def __init__(self, fingerprint, status=ClaimStatus.HIGH_CONFIDENCE):
        self.fingerprint = fingerprint
        self.status = status


def test_blocked_fingerprints_only_includes_high_confidence():
    groups = [
        _Group("a"),
        _Group("b", status=ClaimStatus.PENDING),
        _Group("c", status=ClaimStatus.DISPUTED),
    ]
    assert blocked_fingerprints(groups) == {"a"}


async def test_aggregator_block_set_survives_sweep(demo_repo, defects):
    """闸门降级必须写进聚合器，否则下一次 sweep 会把状态算回去。"""
    engine = _engine(demo_repo, defects)
    first = await engine.run("审查")
    assert first.high_confidence, "前置条件：默认配置下应当有高置信结论"
    fingerprints = {group.fingerprint for group in engine.runtime.ledger.groups()}

    engine.runtime.aggregator.independence_blocked = fingerprints
    groups = engine.runtime.aggregator.sweep()

    assert groups
    assert all(group.status == ClaimStatus.PENDING for group in groups)


# ---- 端到端 ----


def _engine(repo, defects, **overrides) -> ParallaxEngine:
    return ParallaxEngine.build(
        adapter=RepoAdapter(repo, group_depth=2),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_responder(defects)),
        settings=make_settings(**overrides),
    )


async def test_gate_downgrades_high_confidence_when_channels_insufficient(demo_repo, defects):
    # 3 个 Reader 的前提下有效通道数最多为 3，门槛设 3.1 必然不达标。
    engine = _engine(
        demo_repo,
        defects,
        independence_gate="enforce",
        min_effective_channels=3.1,
        max_independence_attempts=0,
    )

    report = await engine.run("审查")

    assert report.manifest.stop_reason.value == "independence_below_budget"
    assert report.high_confidence == []
    assert engine.runtime.gate_decision.action == "downgrade"
    assert engine.runtime.aggregator.independence_blocked
    assert all(
        claim.metadata.get("independence_downgrade")
        for claim in engine.runtime.ledger.claims
        if claim.fingerprint in engine.runtime.aggregator.independence_blocked
    )


async def test_gate_repartitions_once_before_downgrading(demo_repo, defects):
    engine = _engine(
        demo_repo,
        defects,
        independence_gate="enforce",
        min_effective_channels=3.1,
        max_independence_attempts=1,
    )

    report = await engine.run("审查")

    # 第一次不足 → 提高冗余重跑一轮 → 仍不足 → 降级
    assert len(report.manifest.rounds) >= 2
    assert engine.runtime.gate_attempts == 1
    assert report.manifest.stop_reason.value == "independence_below_budget"


async def test_observe_mode_keeps_high_confidence(demo_repo, defects):
    engine = _engine(
        demo_repo,
        defects,
        independence_gate="observe",
        min_effective_channels=3.1,
    )

    report = await engine.run("审查")

    assert report.manifest.stop_reason.value == "coverage_satisfied"
    assert report.high_confidence
    assert engine.runtime.gate_decision.action == "observe"
