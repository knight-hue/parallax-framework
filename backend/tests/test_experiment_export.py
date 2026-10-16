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
