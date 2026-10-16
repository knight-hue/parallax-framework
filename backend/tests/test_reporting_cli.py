"""报告渲染与 CLI 测试。"""

from __future__ import annotations

from parallax.cli import build_parser, main
from parallax.engine import ParallaxEngine
from parallax.infra.llm_fake import FakeLLMClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from parallax.reporting import render_markdown, summarise
from tests.conftest import make_responder, make_settings


async def build_report(repo, defects):
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(repo, group_depth=2),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_responder(defects)),
        settings=make_settings(
            n_readers=3,
            redundancy=2,
            support_threshold=2,
            max_rounds=2,
            seed=1,
            coverage_min_support=2,
        ),
    )
    return await engine.run("审查")


async def test_render_markdown_has_all_sections(demo_repo, defects):
    report = await build_report(demo_repo, defects)
    text = render_markdown(report)

    for heading in (
        "# Parallax 运行报告",
        "## 结论概览",
        "## 运行审计",
        "## 高置信结论",
        "## 待验证（孤证）",
        "## 争议（需裁决）",
        "## 覆盖率矩阵",
    ):
        assert heading in text


async def test_render_markdown_shows_findings_and_sources(demo_repo, defects):
    report = await build_report(demo_repo, defects)
    text = render_markdown(report)

    assert "pkg/mod_a/a.py" in text
    assert "concurrency" in text
    assert "独立来源 2 个" in text


async def test_summarise_is_one_line(demo_repo, defects):
    report = await build_report(demo_repo, defects)
    line = summarise(report)
    assert "\n" not in line
    assert "高置信" in line


async def test_report_serialises_to_json(demo_repo, defects):
    report = await build_report(demo_repo, defects)
    payload = report.model_dump_json()
    assert "manifest" in payload
    assert "coverage" in payload


# ---- CLI ----


def test_parser_defaults():
    args = build_parser().parse_args(["audit", "."])
    assert args.question
    assert args.readers is None
    assert args.visibility is None
    assert args.dry_run is False


def test_parser_rejects_unknown_visibility():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["audit", ".", "--visibility", "whatever"])


def test_cli_dry_run_writes_report(demo_repo, tmp_path, capsys):
    out = tmp_path / "nested" / "report.md"
    code = main(["audit", str(demo_repo), "--dry-run", "--out", str(out), "--group-depth", "2"])

    assert code == 0
    assert out.exists(), "父目录应被自动创建"
    assert "# Parallax 运行报告" in out.read_text(encoding="utf-8")
    assert "[摘要]" in capsys.readouterr().out


def test_cli_requires_api_key_without_dry_run(demo_repo):
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["audit", str(demo_repo)])
    assert "PARALLAX_LLM_API_KEY" in str(exc.value)
