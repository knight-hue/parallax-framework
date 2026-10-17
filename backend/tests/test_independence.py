"""独立性画像、可证伪 Claim 和证据血缘测试。"""

from __future__ import annotations

from parallax.core.independence import build_independence_profile, build_provenance_graph
from parallax.domain.models import Claim, SourceRef


def _claim(agent: str, *, polarity: int = 1) -> Claim:
    return Claim(
        claim_id=f"c-{agent}-{polarity}",
        fingerprint="auth.py#boundary@0",
        statement="输入边界可能未验证",
        polarity=polarity,
        claim_type="boundary",
        extracted_by=agent,
        source_refs=[SourceRef(evidence_id="e1", adapter="test", locator="auth.py:1")],
        trigger_conditions=["攻击者控制输入"],
        counter_conditions=["上游已完成严格校验"],
        reproduction_plan={"input": "empty"},
    )


def test_profile_reports_overlap_and_normalized_channels():
    profile = build_independence_profile(
        [_claim("r0"), _claim("r1")],
        {"r0": ["e1", "e2"], "r1": ["e3", "e4"]},
    )

    assert profile.reader_count == 2
    assert profile.effective_channel_count == 2
    assert profile.normalized_independence == 1
    assert profile.evidence_overlap_rate == 0
    assert profile.isolation_status == "verified"
    assert profile.coverage_fill_rate == 0


def test_profile_has_unknown_isolation_without_readers():
    profile = build_independence_profile([], {})

    assert profile.reader_count == 0
    assert profile.effective_channel_count == 0
    assert profile.isolation_status == "unknown"


def test_profile_records_contamination_and_clamps_coverage():
    profile = build_independence_profile(
        [], {"r0": ["e1"]}, output_contamination=True, coverage_fill_rate=1.5
    )

    assert profile.output_contamination is True
    assert profile.isolation_status == "violated"
    assert profile.coverage_fill_rate == 1


def test_profile_marks_shared_evidence_as_overlap():
    profile = build_independence_profile(
        [_claim("r0")],
        {"r0": ["e1", "e2"], "r1": ["e2", "e3"]},
    )

    assert profile.evidence_overlap_rate > 0
    assert profile.effective_channel_count < 2


def test_profile_counts_distinct_reader_support():
    first = _claim("r0")
    second = _claim("r1")
    second.claim_id = "c-r1-1"
    profile = build_independence_profile(
        [first, second], {"r0": ["e1"], "r1": ["e2"]}
    )
    assert profile.mean_independent_support == 2
    assert profile.claims_with_independent_support == 2

    first.verified_by = ["r0", "r1"]
    profile = build_independence_profile([first], {"r0": ["e1"], "r1": ["e2"]})
    assert profile.mean_independent_support == 2
    assert profile.claims_with_independent_support == 1


def test_provenance_contains_source_reader_claim_and_contradiction():
    graph = build_provenance_graph(
        [_claim("r0"), _claim("r1"), _claim("r2", polarity=-1)],
        {"r0": ["e1"], "r1": ["e2"], "r2": ["e1"]},
    )

    node_types = {node.node_type for node in graph.nodes}
    relations = {edge.relation for edge in graph.edges}
    assert {"evidence", "reader", "claim"} <= node_types
    assert {"reviewed_by", "produced", "derived_from", "supports", "contradicts"} <= relations
