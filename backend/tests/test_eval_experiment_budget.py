"""实验臂预算展开与重复运行的行为测试（不调用真实模型）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parallax.config import Settings
from parallax.eval.corpus import GroundTruth, PlantedDefect, Task
from parallax.eval.experiment import (
    ARMS,
    Arm,
    expand_budgets,
    make_settings,
    run_experiment,
    save_results,
)
from parallax.infra.llm_fake import FakeLLMClient


def test_expand_budgets_is_identity_without_budgets() -> None:
    arms = [a for a in ARMS if a.name in {"baseline_shared", "blind_full"}]
    assert expand_budgets(arms) == arms


def test_expand_budgets_crosses_arms_with_levels() -> None:
    arm = Arm(
        name="blind_full",
        description="",
        visibility="blind",
        redundancy_factor="half",
        max_rounds=1,
    )
    expanded = expand_budgets([arm], calls=[8, 24], tokens=[5000])
    assert [a.name for a in expanded] == [
        "blind_full@calls8@tokens5000",
        "blind_full@calls24@tokens5000",
    ]
    assert [a.max_llm_calls for a in expanded] == [8, 24]
    assert all(a.max_tokens == 5000 for a in expanded)
    # 原有行为不能被预算维度改掉
    assert all(a.redundancy(3) == 2 for a in expanded)


def test_make_settings_only_overrides_budget_when_set() -> None:
    base = Settings(_env_file=None)
    plain = Arm(name="a", description="", visibility="blind", redundancy_factor="one", max_rounds=1)
    assert make_settings(base, plain).max_llm_calls == base.max_llm_calls

    budgeted = Arm(
        name="b",
        description="",
        visibility="blind",
        redundancy_factor="one",
        max_rounds=1,
        max_llm_calls=7,
        max_tokens=1234,
    )
    settings = make_settings(base, budgeted)
    assert settings.max_llm_calls == 7
    assert settings.max_tokens == 1234


def _task(tmp_path: Path) -> Task:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "demo.py"
    source.write_text("def head(values):\n    return values[0]\n", encoding="utf-8")
    defect = PlantedDefect(
        id="d1",
        file="demo.py",
        line_start=2,
        line_end=2,
        defect_class="boundary",
        title="空输入越界",
        marker="return values[0]",
        rationale="空列表会抛 IndexError",
    )
    ground_truth = GroundTruth(task_id="t1", planted_defect_count=1, defects=[defect])
    return Task(
        task_id="t1",
        root=tmp_path,
        repo_path=repo,
        ground_truth=ground_truth,
        question="找出缺陷",
    )


def _factory(_settings):
    return FakeLLMClient(
        responder=lambda _messages: {
            "findings": [
                {
                    "title": "空输入越界",
                    "defect_class": "boundary",
                    "path": "demo.py",
                    "line_start": 2,
                    "line_end": 2,
                    "quote": "return values[0]",
                    "rationale": "空列表会抛 IndexError",
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_repeated_runs_produce_one_directory_per_rep(tmp_path: Path) -> None:
    task = _task(tmp_path)
    arms = [
        Arm(
            name="blind_only",
            description="",
            visibility="blind",
            redundancy_factor="one",
            max_rounds=1,
        )
    ]
    settings = Settings(_env_file=None, n_readers=1, redundancy=1, max_rounds=1)

    for rep in (1, 2):
        results = await run_experiment([task], settings, arms=arms, client_factory=_factory)
        out_dir = tmp_path / f"rep{rep}"
        save_results(results, out_dir)

        payload = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
        assert payload["arms"][0]["arm"] == "blind_only"
        assert payload["arms"][0]["hits"] == 1
        assert payload["arms"][0]["planted"] == 1
        assert (out_dir / "t1__blind_only.claims.json").exists()
        assert (out_dir / "summary.md").exists()
