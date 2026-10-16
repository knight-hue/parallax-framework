"""抽查抽样（纯函数，不需要模型）。

抽样的正确性直接决定抽查结论能不能外推，因此三条约束各有对应测试：
**从完整集合抽**、**分层**、**同种子可复核**。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parallax.eval.spotcheck import (
    BUCKETS,
    counts_by_stratum,
    load_claims,
    render_worksheet,
    sample_claims,
    stratum_of,
    write_outputs,
)


def make_claim(cid: str, status: str, *, sources: int = 1, cls: str = "logic") -> dict:
    return {
        "claim_id": cid,
        "status": status,
        "claim_type": cls,
        "severity": "medium",
        "locator": "pkg/m.py:10-12",
        "statement": f"第 {cid} 条主张",
        "verified_by": [f"reader-{i}" for i in range(sources)],
    }


def pool(sizes: dict[str, int]) -> list[dict]:
    claims: list[dict] = []
    for status, count in sizes.items():
        claims.extend(make_claim(f"{status}-{i}", status) for i in range(count))
    return claims


# ──────────────────────────── 分层 ────────────────────────────


def test_stratum_of_uses_status_and_surfaces_unknown_values():
    assert stratum_of({"status": "high_confidence"}) == "high_confidence"
    assert stratum_of({"status": "pending"}) == "pending"
    # 未知状态必须单独成档而不是被静默丢弃——丢掉的样本会让抽查悄悄失真
    assert stratum_of({"status": "weird"}).startswith("other:")
    assert stratum_of({}).startswith("other:")


def test_counts_by_stratum_covers_every_claim():
    claims = pool({"high_confidence": 3, "pending": 5, "disputed": 2})
    counts = counts_by_stratum(claims)
    assert counts == {"high_confidence": 3, "pending": 5, "disputed": 2}
    assert sum(counts.values()) == len(claims)


# ──────────────────────────── 抽样 ────────────────────────────


def test_sampling_is_stratified_not_proportional():
    """按比例抽会让「争议」几乎抽不到，而它恰恰最需要人看。"""
    claims = pool({"high_confidence": 200, "pending": 100, "disputed": 4})
    samples = sample_claims(claims, {"high_confidence": 15, "pending": 15, "disputed": 10})

    per_bucket = {bucket: sum(1 for s in samples if s.bucket == bucket) for bucket in BUCKETS}
    assert per_bucket == {"high_confidence": 15, "pending": 15, "disputed": 4}


def test_undersized_bucket_takes_everything_instead_of_repeating():
    claims = pool({"disputed": 3})
    samples = sample_claims(claims, {"disputed": 10})
    assert len(samples) == 3
    assert len({s.claim["claim_id"] for s in samples}) == 3, "不允许用重复填补配额"


def test_same_seed_gives_the_same_sample():
    claims = pool({"high_confidence": 50, "pending": 50})
    first = [s.claim["claim_id"] for s in sample_claims(claims, seed=7)]
    second = [s.claim["claim_id"] for s in sample_claims(claims, seed=7)]
    assert first == second, "同输入同种子必须同结果，否则「我们抽了 40 条」无法被复核"


def test_different_seed_gives_a_different_sample():
    claims = pool({"high_confidence": 50, "pending": 50})
    first = {s.claim["claim_id"] for s in sample_claims(claims, seed=1)}
    second = {s.claim["claim_id"] for s in sample_claims(claims, seed=2)}
    assert first != second


def test_empty_pool_yields_nothing_instead_of_raising():
    assert sample_claims([]) == []


# ──────────────────────────── 工作表 ────────────────────────────


def test_worksheet_prints_full_pool_counts_not_just_sample():
    """全集分布必须写出来：它是判断「这次抽样覆不覆盖得到」的一手依据。"""
    claims = pool({"high_confidence": 52, "pending": 646, "disputed": 215})
    text = render_worksheet(sample_claims(claims), claims, title="urllib3")

    assert "646" in text and "215" in text and "52" in text
    assert "完整 claim 集" in text
    assert "不是报告里渲染的那几十条" in text


def test_worksheet_has_a_verdict_column_and_defines_the_scale():
    claims = pool({"high_confidence": 20, "pending": 20})
    text = render_worksheet(sample_claims(claims), claims, title="t")

    assert "| # | 判定 |" in text
    for verdict in ("真缺陷", "误报", "存疑"):
        assert verdict in text
    assert "误报率要如实报告" in text, "必须写明不利结果也要如实报告"


def test_worksheet_escapes_pipes_so_tables_do_not_break():
    claims = [
        {
            **make_claim("x", "pending"),
            "statement": "表达式 a | b 被误读为位运算 | 且这里还有竖线",
        }
    ]
    text = render_worksheet(sample_claims(claims), claims, title="t")
    row = next(line for line in text.splitlines() if "`x`" in line)
    assert "a \\| b" in row, "未转义的竖线会把表格拆成多列"


def test_worksheet_lists_the_seed_for_reproduction():
    claims = pool({"pending": 10})
    text = render_worksheet(sample_claims(claims, seed=12345), claims, title="t", seed=12345)
    assert "12345" in text


# ──────────────────────────── 落盘 ────────────────────────────


def test_write_outputs_produces_worksheet_and_samples(tmp_path: Path):
    claims = pool({"high_confidence": 30, "pending": 30, "disputed": 30})
    source = tmp_path / "run__blind.claims.json"
    source.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")

    worksheet, sample_path = write_outputs(source, tmp_path / "spotcheck")

    assert worksheet.exists() and sample_path.exists()
    assert worksheet.name == "run__blind-worksheet.md"

    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    assert payload["total_claims"] == 90
    assert payload["seed"] == 20261016
    assert payload["strata"] == {"high_confidence": 30, "pending": 30, "disputed": 30}
    assert len(payload["samples"]) == 40, "默认配额应是 15 + 15 + 10"


def test_load_claims_rejects_non_array_payload(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"arms": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="不是 claim 数组"):
        load_claims(bad)
