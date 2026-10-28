"""配对统计的单元测试：口径错一次，整份报告就不可信。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parallax.eval.stats import (
    bootstrap_mean_ci,
    collect_comparisons,
    compare,
    holm,
    mcnemar_exact,
    pair_task,
    sign_flip_p,
    summarise,
)


def test_mcnemar_matches_exact_binomial() -> None:
    # 10 比 0：双侧 p = 2 * (1/2)^10
    assert mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    # 完全对称：p = 1
    assert mcnemar_exact(5, 5) == pytest.approx(1.0)
    # 没有不一致对：p = 1，而不是 0
    assert mcnemar_exact(0, 0) == pytest.approx(1.0)


def test_mcnemar_is_symmetric_in_arguments() -> None:
    assert mcnemar_exact(7, 2) == pytest.approx(mcnemar_exact(2, 7))


def test_mcnemar_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 3)


def test_sign_flip_exact_enumeration_for_small_n() -> None:
    # 6 个差值全为正：2 * (1/2)^6
    assert sign_flip_p([1.0] * 6) == pytest.approx(2 / 64)
    # 有正有负且和接近 0：不显著
    assert sign_flip_p([1.0, -1.0]) == pytest.approx(1.0)
    # 全为 0 时无信息
    assert sign_flip_p([0.0, 0.0]) == pytest.approx(1.0)


def test_sign_flip_is_deterministic_for_large_n() -> None:
    diffs = [1.0] * 25 + [-0.1] * 5
    assert sign_flip_p(diffs) == sign_flip_p(diffs)


def test_bootstrap_ci_brackets_the_mean_and_is_reproducible() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    low, high = bootstrap_mean_ci(values, resamples=2000, seed=7)
    assert low <= 3.0 <= high
    assert (low, high) == bootstrap_mean_ci(values, resamples=2000, seed=7)


def test_bootstrap_ci_degenerate_samples() -> None:
    assert bootstrap_mean_ci([]) == (0.0, 0.0)
    assert bootstrap_mean_ci([2.5]) == (2.5, 2.5)


def test_holm_is_monotone_and_bounded() -> None:
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["c"] == pytest.approx(0.06)
    assert adjusted["b"] == pytest.approx(0.06)
    assert all(value <= 1.0 for value in adjusted.values())


def test_holm_never_decreases_a_p_value() -> None:
    adjusted = holm({"a": 0.5, "b": 0.9})
    assert adjusted["a"] >= 0.5
    assert adjusted["b"] >= 0.9


def _entry(arm: str, task_id: str, defects: dict[str, bool], **extra) -> dict:
    return {
        "arm": arm,
        "task_id": task_id,
        "planted": len(defects),
        "hits": sum(1 for found in defects.values() if found),
        "reader_count": extra.pop("reader_count", 3),
        "prompt_tokens": extra.pop("prompt_tokens", 100),
        "completion_tokens": extra.pop("completion_tokens", 50),
        "effective_channels": extra.pop("effective_channels", 1.0),
        "defects": [
            {"defect_id": key, "found_by": ["r1"] if found else []}
            for key, found in defects.items()
        ],
        **extra,
    }


def test_pair_task_builds_the_four_cell_table() -> None:
    control = _entry("c", "t1", {"d1": True, "d2": True, "d3": False, "d4": False})
    treatment = _entry("x", "t1", {"d1": True, "d2": False, "d3": True, "d4": False})
    paired = pair_task(control, treatment, "t1")
    assert paired is not None
    assert (paired.both, paired.only_control, paired.only_treatment, paired.neither) == (1, 1, 1, 1)
    assert paired.planted == 4
    assert paired.risk_difference == pytest.approx(0.0)


def test_pair_task_reports_unpaired_defects_instead_of_guessing() -> None:
    control = _entry("c", "t1", {"d1": True, "d2": True})
    treatment = _entry("x", "t1", {"d1": True, "d9": True})
    paired = pair_task(control, treatment, "t1")
    assert paired is not None
    assert paired.planted == 1  # 只有 d1 是共同缺陷
    assert paired.unpaired == 2


def test_pair_task_returns_none_without_shared_defects() -> None:
    control = _entry("c", "t1", {"d1": True})
    treatment = _entry("x", "t1", {"d2": True})
    assert pair_task(control, treatment, "t1") is None


def test_summarise_counts_sole_source_and_unanimous() -> None:
    entry = _entry("c", "t1", {"d1": True, "d2": False}, reader_count=3)
    entry["defects"][0]["found_by"] = ["r1"]
    summary = summarise({"t1": entry}, "c")
    assert summary.tasks == 1
    assert summary.sole_source_defects == 1
    assert summary.unanimous_defects == 0
    assert summary.tokens_per_hit == pytest.approx(150.0)


def test_tokens_per_hit_is_none_without_hits() -> None:
    entry = _entry("c", "t1", {"d1": False})
    summary = summarise({"t1": entry}, "c")
    assert summary.tokens_per_hit is None


def _doc(arms: list[dict]) -> dict:
    return {"generated_at": "2026-10-28T00:00:00+00:00", "arms": arms}


def test_compare_skips_failed_arms_and_ignores_tasks_without_ground_truth() -> None:
    doc = _doc(
        [
            _entry("baseline_shared", "t1", {"d1": True, "d2": False}),
            _entry("blind_full", "t1", {"d1": True, "d2": True}),
            # 失败臂必须整条剔除，不能当 0 分
            _entry("blind_full", "t2", {"d3": True}, errors=["boom"]),
            # 无 GT 任务不参与检出率检验
            _entry("blind_full", "real-repo", {}),
            _entry("baseline_shared", "real-repo", {}),
        ]
    )
    comparison = compare(doc, "baseline_shared", "blind_full")
    assert comparison is not None
    assert comparison.planted == 2
    assert (comparison.both, comparison.only_control, comparison.only_treatment) == (1, 0, 1)
    assert comparison.mcnemar_p == pytest.approx(1.0)  # 1 比 1 不显著
    # 方向偏实验组，但 1 个不一致对的证据量不可能显著
    assert comparison.direction() == "实验组更好"
    assert not comparison.significant


def test_compare_detects_a_one_sided_sweep() -> None:
    control = _entry("baseline_shared", "t1", {f"d{i}": False for i in range(10)})
    treatment = _entry("blind_full", "t1", {f"d{i}": True for i in range(10)})
    comparison = compare(_doc([control, treatment]), "baseline_shared", "blind_full")
    assert comparison is not None
    assert comparison.only_treatment == 10
    assert comparison.only_control == 0
    assert comparison.mcnemar_p == pytest.approx(2 / 1024)
    assert comparison.significant
    assert comparison.direction() == "实验组更好"
    low, high = comparison.risk_difference_ci
    assert low > 0 and high <= 1.0


def test_collect_comparisons_reports_skips(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.mkdir()
    (good / "metrics.json").write_text(
        json.dumps(
            _doc(
                [
                    _entry("baseline_shared", "t1", {"d1": False}),
                    _entry("blind_full", "t1", {"d1": True}),
                ]
            )
        ),
        encoding="utf-8",
    )
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "metrics.json").write_text(
        json.dumps(_doc([_entry("baseline_shared", "t1", {"d1": False})])), encoding="utf-8"
    )
    found, skipped = collect_comparisons(
        [good / "metrics.json", bad / "metrics.json"], "baseline_shared", "blind_full"
    )
    assert [label for label, _ in found] == ["good"]
    assert len(skipped) == 1 and "bad" in skipped[0]
