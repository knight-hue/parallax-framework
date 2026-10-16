"""实验产物落盘测试。

重点是 **完整 claim 清单必须落盘**：报告按档位只渲染前 N 条，
若只保存报告，结论质量抽查就只能从被截断的头部抽样，
样本会偏向高置信度，抽查结论无法外推。
"""

from __future__ import annotations

import json

from parallax.eval.corpus import GroundTruth, Task
from parallax.eval.experiment import ARMS, run_arm, save_results
from parallax.infra.llm_fake import FakeLLMClient
from tests.conftest import make_responder, make_settings


def _arm(name: str):
    return next(a for a in ARMS if a.name == name)


def _task(repo) -> Task:
    return Task(
        task_id="demo",
        root=repo,
        repo_path=repo,
        ground_truth=GroundTruth(task_id="demo"),
        question="审查",
    )


async def test_claims_json_contains_every_ledger_entry(demo_repo, defects, tmp_path):
    task = _task(demo_repo)
    result = await run_arm(
        task,
        _arm("baseline_shared"),
        make_settings(n_readers=3, redundancy=2, max_rounds=1),
        client_factory=lambda s: FakeLLMClient(make_responder(defects)),
    )

    save_results([result], tmp_path)
    payload = json.loads(
        (tmp_path / "demo__baseline_shared.claims.json").read_text(encoding="utf-8")
    )

    assert len(payload) == len(result.claims) == result.metrics.total_claims
    assert len(payload) > 0, "演示仓库应产出 claim，否则本测试什么也没验证"

    first = payload[0]
    for key in (
        "claim_id",
        "fingerprint",
        "statement",
        "severity",
        "stance",
        "round_index",
        "verified_by",
        "status",
        "confidence",
        "locator",
    ):
        assert key in first, f"抽查需要字段 {key}"


async def test_claims_json_is_not_capped_by_report_limit(demo_repo, defects, tmp_path):
    """报告上限不得影响落盘条数——这正是当初静默截断造成的隐患。"""
    task = _task(demo_repo)
    result = await run_arm(
        task,
        _arm("baseline_shared"),
        make_settings(n_readers=3, redundancy=2, max_rounds=1, report_max_items=1),
        client_factory=lambda s: FakeLLMClient(make_responder(defects)),
    )

    save_results([result], tmp_path)
    payload = json.loads(
        (tmp_path / "demo__baseline_shared.claims.json").read_text(encoding="utf-8")
    )

    assert len(payload) == len(result.claims)
    assert len(payload) > 1, "需要多于 1 条 claim 才能证明落盘不受报告上限约束"
    assert "仅列出前 1 条" in result.report_markdown


async def test_summary_does_not_confuse_the_two_redundancy_measures(demo_repo, defects):
    """汇总里「冗余率」与「命中同一缺陷的重复」必须分开显示。

    曾经把二者都印成"冗余"：无标注仓库的明细会同时出现「冗余率 63%」和「冗余 0」。
    """
    from parallax.eval.experiment import render_summary

    task = _task(demo_repo)
    result = await run_arm(
        task,
        _arm("baseline_shared"),
        make_settings(n_readers=3, redundancy=2, max_rounds=1),
        client_factory=lambda s: FakeLLMClient(make_responder(defects)),
    )

    text = render_summary([result])
    m = result.metrics

    assert m.distinct_fingerprints is not None, "本仓库运行应记录确切指纹数"
    assert f"独立指纹 {m.distinct_fingerprints}" in text
    assert f"冗余率 {m.redundancy:.0%}" in text
    assert "冗余 0" not in text, "裸数字「冗余」是那个自相矛盾的旧印法"


def test_old_artifacts_without_distinct_fingerprints_render_dash():
    """旧产物没有该字段时不许猜一个数出来。"""
    from parallax.eval.experiment import ArmResult, render_summary
    from parallax.eval.metrics import ArmMetrics

    result = ArmResult(
        metrics=ArmMetrics(arm="baseline_shared", task_id="t", total_claims=100, redundancy=0.63)
    )
    text = render_summary([result])
    assert "独立指纹 —（旧产物未记录）" in text
    assert "独立指纹 0" not in text, "0 会被读成「一条独立结论都没有」"


async def test_rerender_rebuilds_summary_without_rerunning(demo_repo, defects, tmp_path):
    """口径修正后必须能在不重跑实验的前提下刷新汇总表。

    一次两臂真实仓库运行要几美元和近一小时；若刷新一个表格都要重跑，
    口径就会因为"太贵"而长期停留在错误版本。
    """
    from parallax.eval.experiment import rerender_summary

    task = _task(demo_repo)
    result = await run_arm(
        task,
        _arm("baseline_shared"),
        make_settings(n_readers=3, redundancy=2, max_rounds=1),
        client_factory=lambda s: FakeLLMClient(make_responder(defects)),
    )
    out = tmp_path / "run"
    save_results([result], out)

    (out / "summary.md").write_text("被改坏了", encoding="utf-8")
    rerender_summary(out)

    rebuilt = (out / "summary.md").read_text(encoding="utf-8")
    assert "被改坏了" not in rebuilt
    assert f"独立指纹 {result.metrics.distinct_fingerprints}" in rebuilt
    assert "K*" in rebuilt
    # 生效配置也要随 metrics.json 一起回来——它正是"这批数字在什么设置下跑出来的"的全部依据
    assert "生效配置" in rebuilt
    assert "readers=3" in rebuilt
    # 耗时不做断言：假客户端跑得太快，`round(elapsed, 2)` 可能是 0.0，
    # 而 0.0 会被渲染成"不打印耗时"（这是有意的，避免印出误导性的 0.0s）。
    # 断言它会让测试依赖机器速度。
