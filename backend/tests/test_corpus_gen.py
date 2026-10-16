"""语料生成器测试。

重点验证三件不该出错、出错又很难发现的事：
  ① 生成出的源码不能残留泄题标记
  ② ground_truth.json 里的行号必须指向真实的缺陷行
  ③ 生成必须可复现
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parallax.eval.corpus import load_task, verify_task
from parallax.eval.corpus_gen import (
    ARCHETYPES,
    MARKER_RE,
    build_corpus,
    make_variants,
)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    out = tmp_path / "seed_test"
    build_corpus(out_dir=out, task_id="seed_test", variants=make_variants(2))
    return out


def test_no_marker_leaks_into_source(corpus: Path):
    """生成出的源码里不能留下任何 @@D 标记——否则等于直接泄题。"""
    for path in (corpus / "repo").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            assert "@@D" not in line, f"{path.name} 残留标记：{line}"


def test_generated_line_numbers_point_at_defect_lines(corpus: Path):
    payload = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))

    for defect in payload["defects"]:
        path = corpus / "repo" / defect["file"]
        lines = path.read_text(encoding="utf-8").splitlines()
        actual = lines[defect["line_start"] - 1]
        assert defect["marker"] in actual, (
            f"{defect['id']}: 声明的 marker {defect['marker']!r} "
            f"不等于 {defect['file']}:{defect['line_start']} 的实际内容 {actual!r}"
        )


def test_verify_task_passes_on_generated_corpus(corpus: Path):
    assert verify_task(load_task(corpus)) == []


def test_generation_is_deterministic(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    build_corpus(out_dir=a, task_id="t", variants=make_variants(2))
    build_corpus(out_dir=b, task_id="t", variants=make_variants(2))

    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b

    for rel in files_a:
        assert (a / rel).read_text(encoding="utf-8") == (b / rel).read_text(encoding="utf-8")


def test_defect_count_scales_with_variants(corpus: Path):
    payload = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))
    # 6 个原型 × 2 个变体 × 每个原型 1 个缺陷
    assert payload["planted_defect_count"] == len(ARCHETYPES) * 2


def test_every_archetype_contributes_exactly_one_defect_per_instance(tmp_path: Path):
    out = tmp_path / "s"
    payload = build_corpus(out_dir=out, task_id="t", variants=make_variants(1))

    per_file: dict[str, int] = {}
    for defect in payload["defects"]:
        per_file[defect["file"]] = per_file.get(defect["file"], 0) + 1

    assert set(per_file.values()) == {1}, "每个实例文件应恰好包含 1 个植入缺陷"


def test_class_names_differ_across_variants(corpus: Path):
    sources = {
        path.name: path.read_text(encoding="utf-8") for path in (corpus / "repo").rglob("*.py")
    }
    scheduler = {name: src for name, src in sources.items() if name.startswith("scheduler_")}
    assert len(scheduler) == 2

    names = set()
    for src in scheduler.values():
        for line in src.splitlines():
            if line.startswith("class "):
                name = line.split()[1].rstrip(":")
                if not name.startswith("_"):  # 排除模板内部的辅助类型（如 _Item）
                    names.add(name)
    assert names == {"SchedulerAlpha", "SchedulerBeta"}


def test_marker_regex_only_matches_trailing_comments():
    assert MARKER_RE.search("    x = 1  # @@D logic 说明")
    assert not MARKER_RE.search("# @@D 在行首不可靠")  # 行首注释不匹配（模板约定为行尾）
    assert not MARKER_RE.search("    @@D_not_a_comment = 1")


def test_variant_count_is_validated():
    assert len(make_variants(1)) == 1
    with pytest.raises(ValueError):
        make_variants(0)
    with pytest.raises(ValueError):
        make_variants(999)


def test_generated_code_is_valid_python(corpus: Path):
    """标记剥离不能破坏语法——这是生成器最容易被忽略的失败模式。"""
    import ast

    for path in (corpus / "repo").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
