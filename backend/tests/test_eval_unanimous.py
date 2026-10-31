"""`unanimous_defects` 的口径：阈值必须是实际产出者数，而不是跑起来的 Reader 数。"""

from __future__ import annotations

from parallax.eval.metrics import ArmMetrics, DefectOutcome


def _metrics(**kwargs) -> ArmMetrics:
    defaults = {
        "arm": "a",
        "task_id": "t",
        "defects": [
            DefectOutcome(defect_id="d1", title="t1", defect_class="c", file="f.py", found_by=[]),
            DefectOutcome(
                defect_id="d2",
                title="t2",
                defect_class="c",
                file="f.py",
                found_by=["r1", "r2", "r3"],
            ),
            DefectOutcome(
                defect_id="d3",
                title="t3",
                defect_class="c",
                file="f.py",
                found_by=["r1", "r2", "r3", "r4", "r5", "r6"],
            ),
        ],
    }
    defaults.update(kwargs)
    return ArmMetrics(**defaults)


def test_unanimous_uses_agent_count_when_available() -> None:
    """3 轮 × 2 Reader = 6 个 Agent：只有 6 条 found_by 才算全员一致。"""
    metrics = _metrics(reader_count=2, agent_count=6)
    assert metrics.unanimous_defects == 1
    assert metrics.unanimous_threshold_source == "agent"


def test_unanimous_does_not_accept_partial_agreement() -> None:
    """旧实现用 reader_count=2 会把 d2（3 个来源）也算成全员一致，那是错的。"""
    metrics = _metrics(reader_count=2, agent_count=6)
    assert metrics.unanimous_defects != 2


def test_unanimous_falls_back_to_reader_count_for_old_artifacts() -> None:
    metrics = _metrics(reader_count=3, agent_count=0)
    assert metrics.unanimous_defects == 2
    assert metrics.unanimous_threshold_source == "reader"


def test_unanimous_is_zero_without_any_threshold() -> None:
    metrics = _metrics(reader_count=0, agent_count=0)
    assert metrics.unanimous_defects == 0
    assert metrics.unanimous_threshold_source == "missing"


def test_sole_source_counts_single_finder_defects() -> None:
    metrics = _metrics(
        reader_count=3,
        agent_count=3,
        defects=[
            DefectOutcome(
                defect_id="d1", title="t", defect_class="c", file="f.py", found_by=["r1"]
            ),
            DefectOutcome(
                defect_id="d2", title="t", defect_class="c", file="f.py", found_by=["r1", "r2"]
            ),
        ],
    )
    assert metrics.sole_source_defects == 1
