"""重复实验稳定性统计的测试（纯函数，不需要模型）。"""

from __future__ import annotations

import pytest

from parallax.eval.experiment import ArmResult
from parallax.eval.metrics import ArmMetrics
from parallax.eval.variance import Stat, collect, pairwise_verdict, render_variance


def arm_result(
    arm: str,
    *,
    channels: float = 1.0,
    agents: int = 6,
    claims: int = 100,
    redundancy: float = 0.5,
    calls: int = 100,
) -> ArmResult:
    return ArmResult(
        metrics=ArmMetrics(
            arm=arm,
            task_id="t",
            effective_channels=channels,
            agent_count=agents,
            total_claims=claims,
            distinct_fingerprints=int(claims * (1 - redundancy)),
            redundancy=redundancy,
            llm_calls=calls,
        ),
        elapsed_s=12.5,
    )


def repetitions(baseline: list[float], blind: list[float]) -> list[list[ArmResult]]:
    assert len(baseline) == len(blind)
    return [
        [arm_result("baseline_shared", channels=b), arm_result("blind_full", channels=x)]
        for b, x in zip(baseline, blind, strict=True)
    ]


# ---- Stat ----


def test_stat_matches_hand_computed_values():
    s = Stat([1.0, 2.0, 3.0])
    assert s.mean == pytest.approx(2.0)
    assert s.std == pytest.approx(1.0), "样本标准差（ddof=1）"
    assert s.spread == pytest.approx(2.0)


def test_single_sample_has_no_variance():
    s = Stat([5.0])
    assert s.std == 0.0
    assert "n=1" in s.render(), "n=1 必须显式标注，否则会被当成方差为 0 而非未测"


def test_empty_stat_renders_dash():
    assert Stat([]).render() == "—"


# ---- collect ----


def test_collect_keeps_every_repetition():
    stats = collect(repetitions([1.0, 1.2, 0.9], [3.0, 3.4, 2.8]))
    assert stats["baseline_shared"]["effective_channels"].n == 3
    assert stats["baseline_shared"]["effective_channels"].values == [1.0, 1.2, 0.9]
    assert stats["blind_full"]["channels_ratio"].values == pytest.approx(
        [0.5, 3.4 / 6, 2.8 / 6], abs=1e-4
    ), "channels_ratio 保留 4 位小数"


def test_a_failed_arm_is_excluded_not_counted_as_zero():
    """某次重复里某臂失败时，不参与统计。

    当 0 处理会把均值无端拉低——这正是本项目一直在修的那类"看起来真实的错误数字"。
    """
    good = [arm_result("baseline_shared", channels=2.0, calls=100)] * 2
    failed = [arm_result("baseline_shared", channels=0.0, agents=0, claims=0, calls=0)]
    stats = collect([good, failed[:0], [arm_result("blind_full", channels=3.0)]])

    assert stats["baseline_shared"]["effective_channels"].values == [2.0, 2.0]
    assert stats["baseline_shared"]["effective_channels"].mean == 2.0


# ---- 稳定性判定 ----


def test_verdict_stable_when_gap_exceeds_noise_twice_over():
    lines = pairwise_verdict(
        collect(repetitions([1.00, 1.02, 0.98], [1.50, 1.52, 1.48])), "baseline_shared", "blind_full"
    )
    assert any("判定：稳定" in ln for ln in lines)
    assert any("逐次差距" in ln for ln in lines)


def test_verdict_hedges_when_direction_is_consistent_but_noise_is_large():
    """每次都同向但幅度未与波动拉开时，必须说"不能排除偶然"，不能说"稳定"。"""
    lines = pairwise_verdict(
        collect(repetitions([0.0, 1.0, 0.0], [5.0, 2.0, 5.0])), "baseline_shared", "blind_full"
    )
    text = "\n".join(lines)
    assert "方向一致" in text
    assert "不能排除偶然" in text
    assert "判定：稳定" not in text


def test_verdict_reports_instability_when_a_repetition_reverses():
    lines = pairwise_verdict(
        collect(repetitions([1.0, 3.0, 1.0], [2.0, 2.0, 2.0])), "baseline_shared", "blind_full"
    )
    text = "\n".join(lines)
    assert "不稳定" in text
    assert "出现了方向相反的重复" in text


def test_verdict_refuses_when_single_repetition():
    lines = pairwise_verdict(
        collect(repetitions([1.0], [3.0])), "baseline_shared", "blind_full"
    )
    assert any("重复次数不足" in ln for ln in lines)


def test_verdict_refuses_when_arm_missing():
    lines = pairwise_verdict(collect(repetitions([1.0, 2.0], [3.0, 4.0])), "baseline_shared", "nope")
    assert any("缺少" in ln for ln in lines)


def test_verdict_refuses_on_uneven_arm_counts():
    """两臂有效次数不同时逐次配对无意义，必须拒绝而不是拿短的截断。"""
    stats = collect(repetitions([1.0, 1.1], [3.0, 3.1]))
    stats["blind_full"]["effective_channels"] = Stat([3.0, 3.1, 3.2])
    lines = pairwise_verdict(
        stats, "baseline_shared", "blind_full", metric="effective_channels"
    )
    assert any("有效次数不同" in ln for ln in lines)


# ---- 渲染 ----


def test_render_contains_disclaimer_about_no_significance_test():
    text = render_variance(repetitions([1.0, 1.1, 0.9], [3.0, 3.2, 2.8]), repo="urllib3")
    assert "# 重复实验的稳定性" in text
    assert "urllib3" in text
    assert "为什么不做显著性检验" in text, "必须解释为何给区间而不给 p 值"
    assert "样本标准差" in text


def test_render_lists_every_repetition_value():
    text = render_variance(repetitions([1.0, 1.1, 0.9], [3.0, 3.2, 2.8]))
    for value in ("1.00", "1.10", "0.90", "3.00", "3.20", "2.80"):
        assert value in text
