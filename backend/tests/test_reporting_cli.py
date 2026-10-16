"""报告渲染与 CLI 测试。"""

from __future__ import annotations

from parallax.cli import build_parser, main
from parallax.domain.enums import ClaimStatus
from parallax.domain.models import Claim, SourceRef
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


# ---- 报告截断必须显式（曾静默只渲染前 40 条） ----


def _claim(i: int, status: ClaimStatus) -> Claim:
    return Claim(
        claim_id=f"c{i}",
        fingerprint=f"fp-{i}",
        statement=f"第 {i} 条主张",
        claim_type="concurrency",
        extracted_by=f"reader-r0-{i}",
        source_refs=[
            SourceRef(
                adapter="test",
                evidence_id=f"e{i}",
                locator=f"pkg/m{i}.py",
                line_start=1,
            )
        ],
        verified_by=[f"reader-r0-{i}"],
        status=status,
        confidence=0.5,
        metadata={"severity": "high"},
    )


def test_truncated_bucket_announces_true_count_and_limit():
    from parallax.reporting import _render_claims

    claims = [_claim(i, ClaimStatus.PENDING) for i in range(123)]
    text = "\n".join(_render_claims("待验证（孤证）", claims, 40))

    assert "共 **123** 条" in text, "截断必须报出真实条数，否则读者会以为总数就是上限"
    assert "仅列出前 40 条" in text
    assert "claims.json" in text


def test_bucket_below_limit_has_no_truncation_notice():
    from parallax.reporting import _render_claims

    claims = [_claim(i, ClaimStatus.PENDING) for i in range(5)]
    text = "\n".join(_render_claims("待验证（孤证）", claims, 40))

    assert "仅列出前" not in text
    assert text.count("- **") == 5


def test_zero_limit_means_unlimited():
    from parallax.reporting import _render_claims

    claims = [_claim(i, ClaimStatus.PENDING) for i in range(57)]
    text = "\n".join(_render_claims("待验证（孤证）", claims, 0))

    assert "仅列出前" not in text
    assert text.count("- **") == 57


async def test_render_markdown_honours_max_items(demo_repo, defects):
    report = await build_report(demo_repo, defects)
    text = render_markdown(report, max_items=1)

    bucket = len(report.pending) + len(report.disputed) + len(report.high_confidence)
    if bucket > 1:
        assert "仅列出前 1 条" in text, "经 render_markdown 的截断同样必须显式"
    assert "## 覆盖率矩阵" in text


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
