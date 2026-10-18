"""自适应补检排序测试。"""

from parallax.core.scheduling import AdaptiveFocusScheduler


def test_scheduler_prioritises_hard_gaps_then_disputes_deterministically():
    scheduler = AdaptiveFocusScheduler()
    assert scheduler.rank(
        ["z", "a", "m"],
        uncovered_rows=["m"],
        dispute_rows=["a"],
        unconfirmed_rows=["z"],
    ) == ["m", "a", "z"]


def test_scheduler_breaks_equal_scores_by_row_name():
    scheduler = AdaptiveFocusScheduler()
    assert scheduler.rank(["b", "a"], unconfirmed_rows=["b", "a"]) == ["a", "b"]
