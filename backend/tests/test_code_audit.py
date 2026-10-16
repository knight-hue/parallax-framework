"""代码审查插件测试：仓库适配器 + Reader 解析与指纹。"""

from __future__ import annotations

import pytest

from parallax.domain.errors import AdapterError, SchemaValidationError
from parallax.plugins.code_audit import DEFECT_CLASSES, CodeAuditReader, RepoAdapter

# ---- 适配器 ----


def test_adapter_reads_and_groups_by_module(demo_repo):
    adapter = RepoAdapter(demo_repo, group_depth=2)
    units = adapter.load("审查")

    assert len(units) == 3
    assert adapter.dimension_rows(units) == ["pkg/mod_a", "pkg/mod_b"]
    assert {u.group for u in units} == {"pkg/mod_a", "pkg/mod_b"}


def test_adapter_evidence_ids_are_stable(demo_repo):
    """证据 id 必须稳定，否则 run manifest 无法复盘。"""
    first = RepoAdapter(demo_repo).load("q")
    second = RepoAdapter(demo_repo).load("q")
    assert [u.evidence_id for u in first] == [u.evidence_id for u in second]


def test_adapter_excludes_noise_dirs(demo_repo):
    (demo_repo / "__pycache__").mkdir()
    (demo_repo / "__pycache__" / "junk.py").write_text("x = 1\n", encoding="utf-8")
    (demo_repo / "node_modules").mkdir()
    (demo_repo / "node_modules" / "dep.py").write_text("y = 1\n", encoding="utf-8")

    units = RepoAdapter(demo_repo, group_depth=2).load("q")
    locators = {u.locator for u in units}
    assert not any("__pycache__" in loc for loc in locators)
    assert not any("node_modules" in loc for loc in locators)


def test_adapter_rejects_empty_scope(tmp_path):
    (tmp_path / "readme.txt").write_text("nothing", encoding="utf-8")
    with pytest.raises(AdapterError):
        RepoAdapter(tmp_path).load("q")


def test_adapter_rejects_missing_root(tmp_path):
    with pytest.raises(AdapterError):
        RepoAdapter(tmp_path / "nope")


# ---- Reader ----


def finding(**overrides) -> dict:
    base = {
        "title": "空列表越界",
        "defect_class": "boundary",
        "path": "pkg/mod_b/b.py",
        "line_start": 2,
        "line_end": 2,
        "severity": "medium",
        "stance": "defect",
        "rationale": "空输入会 IndexError",
        "quote": "    return items[0]",
    }
    base.update(overrides)
    return base


def shard_for(demo_repo):
    return RepoAdapter(demo_repo, group_depth=2).load("q")


def test_claim_types_define_matrix_columns():
    assert CodeAuditReader().claim_types() == DEFECT_CLASSES


def test_parse_builds_claim_with_source_ref(demo_repo):
    reader = CodeAuditReader()
    shard = shard_for(demo_repo)
    claims = reader.parse({"findings": [finding()]}, shard, "reader-r0-0", 0, 0.5)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.claim_type == "boundary"
    assert claim.polarity == 1
    assert claim.source_refs[0].locator == "pkg/mod_b/b.py:2-2"
    assert claim.reputation_at_extraction == 0.5
    assert claim.metadata["severity"] == "medium"


def test_fingerprint_tolerates_line_drift(demo_repo):
    """两个 Reader 对同一条缺陷报的行号不会完全一致，指纹必须能容忍。"""
    reader = CodeAuditReader(line_bucket=20)
    shard = shard_for(demo_repo)
    a = reader.parse({"findings": [finding(line_start=2, line_end=2)]}, shard, "r1", 0, 0.5)
    b = reader.parse({"findings": [finding(line_start=15, line_end=17)]}, shard, "r2", 0, 0.5)
    assert a[0].fingerprint == b[0].fingerprint


def test_fingerprint_separates_distant_locations(demo_repo):
    reader = CodeAuditReader(line_bucket=20)
    shard = shard_for(demo_repo)
    a = reader.parse({"findings": [finding(line_start=2, line_end=2)]}, shard, "r1", 0, 0.5)
    b = reader.parse({"findings": [finding(line_start=105, line_end=106)]}, shard, "r2", 0, 0.5)
    assert a[0].fingerprint != b[0].fingerprint


def test_fingerprint_separates_defect_classes(demo_repo):
    reader = CodeAuditReader()
    shard = shard_for(demo_repo)
    a = reader.parse({"findings": [finding(defect_class="boundary")]}, shard, "r1", 0, 0.5)
    b = reader.parse({"findings": [finding(defect_class="security")]}, shard, "r2", 0, 0.5)
    assert a[0].fingerprint != b[0].fingerprint


def test_not_a_defect_becomes_deny_polarity(demo_repo):
    """「我看着可疑但其实是安全的」必须成为反极性主张，否则永远产生不了争议。"""
    reader = CodeAuditReader()
    shard = shard_for(demo_repo)
    claims = reader.parse({"findings": [finding(stance="not_a_defect")]}, shard, "r1", 0, 0.5)
    assert claims[0].polarity == -1


def test_unauthorized_path_is_dropped(demo_repo):
    reader = CodeAuditReader()
    shard = shard_for(demo_repo)
    claims = reader.parse(
        {
            "findings": [
                finding(),
                finding(path="totally/made/up.py"),
            ]
        },
        shard,
        "r1",
        0,
        0.5,
    )
    assert len(claims) == 1


def test_all_unauthorized_paths_raise_for_retry(demo_repo):
    """全部路径都是编造的 → 当作格式失败重问，而不是静默返回空。"""
    reader = CodeAuditReader()
    shard = shard_for(demo_repo)
    with pytest.raises(SchemaValidationError):
        reader.parse({"findings": [finding(path="made/up.py")]}, shard, "r1", 0, 0.5)


def test_unknown_defect_class_falls_back(demo_repo):
    reader = CodeAuditReader()
    shard = shard_for(demo_repo)
    claims = reader.parse(
        {"findings": [finding(defect_class="not-a-real-class")]}, shard, "r1", 0, 0.5
    )
    assert claims[0].claim_type == "logic"


def test_prompt_contains_only_shard_and_lists_paths(demo_repo):
    """盲读契约：提示词里只能出现本 Reader 分到的文件。"""
    reader = CodeAuditReader()
    units = shard_for(demo_repo)
    only_a = [u for u in units if u.group == "pkg/mod_a"]

    messages = reader.build_messages("审查", only_a, "r1")
    text = "\n".join(m.content for m in messages)

    assert "===== FILE: pkg/mod_a/a.py =====" in text
    assert "pkg/mod_b" not in text


def test_large_file_is_truncated_with_notice(demo_repo):
    reader = CodeAuditReader(max_prompt_chars=4_000)
    big = shard_for(demo_repo)[0]
    rendered = reader._render_unit(big, budget=100)  # noqa: SLF001
    assert "已截断" in rendered
