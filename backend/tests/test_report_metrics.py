"""报告渲染与 /metrics 导出的单元测试。

两件事必须成立：
1. Markdown 报告要包含闸门判定与缺口归因——JSON 有而 Markdown 没有，会让 CLI 用户看不到新机制；
2. `/metrics` 只导出真实存在的指标，且状态计数与存储一致。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from parallax.domain.enums import RoundStopReason
from parallax.domain.models import Report, RunManifest
from parallax.reporting import render_markdown
from parallax.service.app import create_app
from parallax.service.metrics import render_prometheus
from parallax.service.store import RunRecord, RunStore
from tests.conftest import make_settings


def _report(**overrides) -> Report:
    manifest = RunManifest(
        run_id="run-1",
        question="审查这个仓库",
        plugin="code-audit",
        seed=1,
        max_rounds=2,
        support_threshold=2,
        stop_reason=RoundStopReason.INDEPENDENCE_BELOW_BUDGET,
    )
    payload = {
        "run_id": "run-1",
        "question": "审查这个仓库",
        "manifest": manifest,
        "gate": {
            "action": "downgrade",
            "reason": "独立性不足（有效通道 1.20 < 2.60）且重分区尝试已用尽",
            "attempts": 1,
            "effective_channels": 1.2,
            "normalized_independence": 0.4,
        },
        "gap_attribution": {
            "min_support": 2,
            "by_kind": {"reader_miss": 2, "healthy": 3},
            "actionable_groups": ["mod-a"],
            "run_estimate": {
                "observed": 6,
                "estimated_total": 8.0,
                "detection_probability": 0.75,
                "recapture_pairs": 3,
                "method": "chapman-median",
            },
            "items": [
                {
                    "evidence_id": "mod-a/a.py",
                    "group": "mod-a",
                    "readers": 3,
                    "claims": 0,
                    "kind": "reader_miss",
                    "reason": "3 个 Reader 均未报出",
                    "missing_probability": 0.0156,
                }
            ],
        },
    }
    payload.update(overrides)
    return Report(**payload)


# ---- Markdown 报告 ----


def test_report_renders_gate_section():
    text = render_markdown(_report())
    assert "## 独立性准入闸门" in text
    assert "结论已降级为待验证" in text
    assert "不得当作高置信采信" in text
    assert "有效通道：1.20" in text


def test_report_renders_gap_attribution_section():
    text = render_markdown(_report())
    assert "## 覆盖缺口归因" in text
    assert "漏检候选（读者层）：2" in text
    assert "75.0%" in text
    assert "`mod-a/a.py`" in text
    assert "漏检候选，不是缺陷结论" in text


def test_report_omits_sections_when_payload_empty():
    text = render_markdown(_report(gate={}, gap_attribution={}))
    assert "## 独立性准入闸门" not in text
    assert "## 覆盖缺口归因" not in text


def test_report_handles_unestimable_detection_probability():
    gap = {
        "by_kind": {"unresolved": 2},
        "run_estimate": {
            "observed": 0,
            "estimated_total": None,
            "detection_probability": None,
            "recapture_pairs": 0,
            "method": "chapman-median",
        },
        "items": [
            {
                "evidence_id": "mod-b/b.py",
                "group": "mod-b",
                "readers": 3,
                "claims": 0,
                "kind": "unresolved",
                "reason": "零检出且无重捕",
                "missing_probability": None,
            }
        ],
    }
    text = render_markdown(_report(gap_attribution=gap))
    assert "无法估计（无重捕" in text
    assert "| `mod-b/b.py` | 3 | 0 | `unresolved` | — |" in text


# ---- /metrics ----


def test_prometheus_text_has_types_and_zero_filled_statuses():
    text = render_prometheus([], version="9.9.9", active_leases=0)
    assert "# TYPE parallax_up gauge" in text
    assert 'parallax_build_info{version="9.9.9"} 1' in text
    assert 'parallax_runs{status="failed"} 0' in text
    assert "parallax_runs_total 0" in text
    assert "parallax_active_leases 0" in text
    assert text.endswith("\n")


def test_prometheus_text_counts_statuses():
    statuses = ["done", "done", "running", "failed", "weird"]
    text = render_prometheus(statuses, version="1", active_leases=1)
    assert 'parallax_runs{status="done"} 2' in text
    assert 'parallax_runs{status="running"} 1' in text
    assert 'parallax_runs{status="failed"} 1' in text
    assert 'parallax_runs{status="weird"} 1' in text
    assert "parallax_runs_total 5" in text


def test_metrics_endpoint_serves_exposition(tmp_path):
    app = create_app(make_settings(), runs_dir=tmp_path)
    store: RunStore = app.state.store
    store.create(RunRecord(run_id="r1", question="q", status="done"))
    store.create(RunRecord(run_id="r2", question="q", status="failed"))

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert 'parallax_runs{status="done"} 1' in body
    assert 'parallax_runs{status="failed"} 1' in body
    assert "parallax_runs_total 2" in body
