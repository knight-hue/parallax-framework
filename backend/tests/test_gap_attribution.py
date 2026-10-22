"""覆盖缺口归因的单元测试。

要点：
1. 无重捕时**不发数字**（Chapman 发散，硬凑就是伪造精度）；
2. 分区缺口与读者漏检被区分开，处置不同（补派 vs 估漏检）；
3. 零检出在无运行级标定时停在 unresolved，不硬判成漏检；
4. 检出率有上限，不出现"p=1 所以绝不会漏"的伪确定性。
"""

from __future__ import annotations

import random

import pytest

from parallax.core.gap_attribution import (
    attribute_gaps,
    chapman,
    estimate_capture,
)
from parallax.domain.models import Claim, SourceRef


def _claim(fingerprint: str, reader: str, evidence_id: str) -> Claim:
    return Claim(
        claim_id=f"{fingerprint}:{reader}",
        fingerprint=fingerprint,
        statement=f"{fingerprint}",
        claim_type="generic",
        extracted_by=reader,
        source_refs=[SourceRef(evidence_id=evidence_id, adapter="test", locator=evidence_id)],
    )


# ---- Chapman ----


def test_chapman_matches_textbook_value():
    # n1=n2=20, m=10 -> (21*21)/11 - 1 = 39.0909...
    assert chapman(20, 20, 10) == pytest.approx(39.090909, rel=1e-6)


def test_chapman_returns_none_without_recapture():
    assert chapman(5, 5, 0) is None
    assert chapman(0, 5, 0) is None


def test_estimate_requires_two_detecting_readers():
    estimate = estimate_capture({"r1": {"a", "b"}, "r2": set()})
    assert estimate.estimated_total is None
    assert estimate.detection_probability is None
    assert estimate.miss_rate is None
    assert estimate.observed == 2


def test_estimate_is_capped_below_certainty():
    """三人全部报出同一批指纹时，覆盖率恰好 100%——不能因此宣称 p=1。"""
    population = {f"d{i}" for i in range(8)}
    estimate = estimate_capture({"r1": population, "r2": population, "r3": population})
    assert estimate.detection_probability == pytest.approx(0.95)
    assert estimate.estimated_total == 8


def test_estimate_recovers_population_within_tolerance():
    population = [f"d{i}" for i in range(40)]
    rng = random.Random(42)
    samples = {f"r{i}": {item for item in population if rng.random() < 0.6} for i in range(3)}
    estimate = estimate_capture(samples)
    assert estimate.estimated_total is not None
    assert abs(estimate.estimated_total - 40) / 40 <= 0.25


# ---- 归因 ----


def test_partition_gap_when_not_enough_readers():
    report = attribute_gaps(
        assignments={"r1": ["e1"], "r2": ["e1"]},
        claims=[],
        groups={"e1": "mod"},
        min_support=3,
    )
    assert report.partition_gap_count == 1
    item = report.items[0]
    assert item.kind == "partition_gap"
    assert item.needs_more_readers is True
    assert report.actionable_groups == ["mod"]


def test_healthy_when_claims_exist():
    report = attribute_gaps(
        assignments={"r1": ["e1"], "r2": ["e1"], "r3": ["e1"]},
        claims=[_claim("f1", "r1", "e1"), _claim("f1", "r2", "e1")],
        groups={"e1": "mod"},
        min_support=3,
    )
    assert report.by_kind == {"healthy": 1}


def test_reader_miss_when_zero_detection_and_high_run_detection_rate():
    # 运行级：两个 Reader 重捕充分，p̄ 高；第三条证据三人全零检出。
    claims = [_claim(f"f{i}", reader, "e1") for reader in ("r1", "r2", "r3") for i in range(6)]
    report = attribute_gaps(
        assignments={reader: ["e1", "e2"] for reader in ("r1", "r2", "r3")},
        claims=claims,
        groups={"e1": "mod-a", "e2": "mod-b"},
        min_support=3,
    )
    kinds = {item.evidence_id: item.kind for item in report.items}
    assert kinds["e1"] == "healthy"
    assert kinds["e2"] == "reader_miss"
    miss = next(item for item in report.items if item.evidence_id == "e2")
    assert miss.missing_probability is not None
    assert miss.missing_probability < 0.5
    assert "漏检候选" in miss.reason


def test_unresolved_when_no_calibration_available():
    report = attribute_gaps(
        assignments={reader: ["e1"] for reader in ("r1", "r2", "r3")},
        claims=[],
        groups={"e1": "mod"},
        min_support=3,
    )
    assert report.by_kind == {"unresolved": 1}
    assert report.by_kind.get("reader_miss", 0) == 0
    assert report.run_estimate.detection_probability is None


def test_actionable_groups_deduplicate():
    report = attribute_gaps(
        assignments={"r1": ["e1", "e2"]},
        claims=[],
        groups={"e1": "same", "e2": "same"},
        min_support=3,
    )
    assert report.actionable_groups == ["same"]
