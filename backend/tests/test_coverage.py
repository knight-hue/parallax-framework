"""覆盖率监控测试——机制 4 的核心行为。"""

from __future__ import annotations

from parallax.core.coverage import CoverageMonitor
from parallax.domain.enums import RoundStopReason
from parallax.domain.models import CoverageMatrix
from tests.conftest import make_unit

ROWS = ["mod_a", "mod_b"]
COLS = ["logic", "concurrency", "boundary"]


def units():
    return {
        "e_a1": make_unit("mod_a/a.py", "# a1", "mod_a"),
        "e_a2": make_unit("mod_a/c.py", "# a2", "mod_a"),
        "e_b1": make_unit("mod_b/b.py", "# b1", "mod_b"),
    }


def matrix_with(cells: dict[tuple[str, str], int]) -> CoverageMatrix:
    m = CoverageMatrix(rows=list(ROWS), cols=list(COLS))
    for (row, col), n in cells.items():
        m.add(row, col, n)
    return m


# ---- 矩阵 ----


def test_rows_and_cols_are_preseeded():
    """一个毫无 claim 的模块也必须出现在矩阵里，否则最严重的空洞会被漏掉。"""
    m = matrix_with({})
    assert m.rows == ROWS
    assert m.cols == COLS
    assert m.fill_rate() == 0.0


def test_sparse_vs_unconfirmed_are_different():
    """这是本模块最要紧的语义区分。"""
    m = matrix_with({("mod_a", "logic"): 1, ("mod_b", "boundary"): 2})

    # 少有人报的（含完全没人报的）
    assert ("mod_a", "logic") in m.sparse_cells(min_support=2)
    assert ("mod_b", "logic") in m.sparse_cells(min_support=2)

    # 有人报但未获确认——才是补检该盯的目标
    unconfirmed = m.unconfirmed_cells(min_support=2)
    assert unconfirmed == [("mod_a", "logic")]
    # 零主张的格子不算「未确认」，否则补检永远不收敛
    assert ("mod_b", "logic") not in unconfirmed


def test_cell_counts_are_deterministic_and_sorted():
    m = matrix_with({("mod_b", "logic"): 1, ("mod_a", "logic"): 1})
    assert m.sparse_cells(min_support=3) == sorted([(r, c) for r in ROWS for c in COLS])


# ---- 证据覆盖 ----


def test_evidence_fill_rate_counts_distinct_readers():
    monitor = CoverageMonitor(min_support=2)
    units_map = units()
    assignments = {
        "reader-r0-0": ["e_a1", "e_a2", "e_b1"],
        "reader-r0-1": ["e_a1", "e_a2"],
    }
    # e_b1 只被 1 个 Reader 看过 → 2/3 达标
    assert abs(monitor.evidence_fill_rate(assignments, list(units_map)) - 2 / 3) < 1e-9


def test_row_support_uses_minimum_not_average():
    """模块里只要有一个文件没被看够，整个模块就不算覆盖达标。"""
    monitor = CoverageMonitor(min_support=2)
    units_map = units()
    assignments = {
        "reader-r0-0": ["e_a1", "e_a2", "e_b1"],
        "reader-r0-1": ["e_a1", "e_b1"],  # 漏看了 e_a2
    }
    per_row, uncovered = monitor.row_support(assignments, units_map, ROWS)
    assert per_row["mod_a"] == 1  # 因为 e_a2 只被看了 1 次
    assert per_row["mod_b"] == 2
    assert uncovered == ["mod_a"]


def test_reader_ids_are_round_scoped_so_rounds_accumulate():
    monitor = CoverageMonitor(min_support=2)
    assignments = {
        "reader-r0-0": ["e_a1"],
        "reader-r1-0": ["e_a1"],  # 第 1 轮的新 Reader
    }
    assert monitor.evidence_fill_rate(assignments, ["e_a1"]) == 1.0


# ---- 研判 ----


def monitor() -> CoverageMonitor:
    return CoverageMonitor(min_support=2, min_evidence_fill_rate=1.0, max_dispute_rate=0.5)


def test_budget_stops_first():
    d = monitor().decide(
        matrix_with({}),
        round_index=0,
        max_rounds=5,
        budget_exhausted=True,
    )
    assert not d.should_retrieve
    assert d.stop_reason == RoundStopReason.BUDGET_EXHAUSTED


def test_max_rounds_stops():
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 1}),
        round_index=2,
        max_rounds=3,
    )
    assert d.stop_reason == RoundStopReason.MAX_ROUNDS_REACHED


def test_no_progress_stops_after_a_retrieval_round():
    """补检了一轮却没有任何新主体 → 说明查透了，继续只是烧钱。"""
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 1}),
        round_index=1,
        max_rounds=5,
        new_fingerprints_last_round=0,
    )
    assert d.stop_reason == RoundStopReason.NO_NEW_EVIDENCE


def test_satisfied_when_nothing_to_fix():
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 2}),
        round_index=0,
        max_rounds=5,
        evidence_fill_rate=1.0,
        new_fingerprints_last_round=1,
    )
    assert not d.should_retrieve
    assert d.stop_reason == RoundStopReason.COVERAGE_SATISFIED


def test_unconfirmed_cell_is_a_hint_not_a_trigger():
    """有人报出但无人确认的格子只是**聚焦提示**，不单独触发补检。

    若让它单独触发，补检会永不收敛：多数模块本来就不具备全部缺陷类型，
    那些格子永远凑不满 min_support，每一轮都能找到"新的待确认项"。
    """
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 1}),
        round_index=0,
        max_rounds=5,
        evidence_fill_rate=1.0,
        new_fingerprints_last_round=1,
    )
    assert not d.should_retrieve
    assert d.stop_reason == RoundStopReason.COVERAGE_SATISFIED


def test_unconfirmed_cell_joins_focus_when_retrieval_already_triggered():
    """但一旦因为别的原因要补检，这些格子会被纳入聚焦范围。"""
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 1}),
        round_index=0,
        max_rounds=5,
        evidence_fill_rate=0.5,
        uncovered_rows=["mod_b"],
        new_fingerprints_last_round=1,
    )
    assert d.should_retrieve
    assert "mod_b" in d.focus_groups  # 触发源
    assert "mod_a" in d.focus_groups  # 聚焦提示


def test_retrieves_for_uncovered_rows():
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 2}),
        round_index=0,
        max_rounds=5,
        evidence_fill_rate=0.5,
        uncovered_rows=["mod_b"],
        new_fingerprints_last_round=1,
    )
    assert d.should_retrieve
    assert d.focus_groups == ["mod_b"]
    assert d.uncovered_rows == ["mod_b"]


def test_retrieves_for_disputes():
    d = monitor().decide(
        matrix_with({("mod_a", "logic"): 2}),
        round_index=0,
        max_rounds=5,
        evidence_fill_rate=1.0,
        dispute_rows=["mod_b"],
        new_fingerprints_last_round=1,
    )
    assert d.should_retrieve
    assert "mod_b" in d.focus_groups
