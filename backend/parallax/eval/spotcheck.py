"""结论质量抽查：从完整 claim 集里**分层随机抽样**，产出可逐条判定的工作表。

## 为什么必须有这一步

K\\*、冗余率、覆盖率测的都是"Agent 之间有多独立"，**没有一个指标能回答
"这些结论本身对不对"**。对错需要人拿着源码一条条核对。
不抽查就只有一个漂亮的结构性指标，而评审最想问的恰恰是"它报出来的东西准不准"。

## 三条方法约束

1. **必须从完整集合抽样，而不是从报告里抽。**
   报告按档位只渲染前 40 条（高置信在前），从报告抽会系统性偏向高置信度，
   抽查精度会被高估——这不是理论风险，正是加 `claims.json` 落盘的原因。
2. **分层**：高置信 / 待验证 / 争议各抽固定条数。
   按比例抽会让"争议"这种占比极小的档位几乎抽不到，而它恰恰最需要人看。
3. **确定性**：同一份 claim 集 + 同一个种子 → 同一批样本。
   否则"我们抽了 40 条"这句话无法被任何人复核。

判定口径（写进工作表表头，避免各人理解不同）：
- `真缺陷`：能在源码中指出具体触发路径
- `误报`：描述与代码不符，或属风格/主观偏好而非缺陷
- `存疑`：无法确认（证据不足、依赖运行时条件）
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: 抽查的三个档位，与 ClaimStatus 的取值一致。
BUCKETS: tuple[str, ...] = ("high_confidence", "pending", "disputed")

#: 默认抽样条数：高置信 15 / 待验证 15 / 争议 10 = 40 条。
#: 高置信与待验证各 15 是为了让两档的精度对比有最低限度的样本量；
#: 争议只抽 10 是因为它总量本来最少，抽更多也只是重复同一批。
DEFAULT_PER_BUCKET: dict[str, int] = {"high_confidence": 15, "pending": 15, "disputed": 10}

VERDICTS = ("真缺陷", "误报", "存疑")


@dataclass(frozen=True)
class Sample:
    bucket: str
    claim: dict[str, Any]


def load_claims(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} 不是 claim 数组；请用 save_results 产出的 *.claims.json")
    return payload


def stratum_of(claim: dict[str, Any]) -> str:
    """把一条 claim 归到某个档位。未知状态单独归入 `other`，不静默丢弃。"""
    status = str(claim.get("status") or "").strip()
    return status if status in BUCKETS else f"other:{status or 'missing'}"


def counts_by_stratum(claims: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(stratum_of(c) for c in claims))


def sample_claims(
    claims: list[dict[str, Any]],
    per_bucket: dict[str, int] | None = None,
    seed: int = 20261016,
) -> list[Sample]:
    """分层随机抽样。**确定性**：同输入同种子必得同结果。

    某一档不足配额时抽全部并在工作表里注明——缺样本是事实，
    不该用重复填补把它抹平。
    """
    quota = dict(DEFAULT_PER_BUCKET)
    if per_bucket:
        quota.update(per_bucket)

    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        grouped.setdefault(stratum_of(claim), []).append(claim)

    samples: list[Sample] = []
    for bucket, size in quota.items():
        pool = grouped.get(bucket, [])
        if not pool:
            continue
        picked = rng.sample(pool, min(size, len(pool)))
        samples.extend(Sample(bucket, claim) for claim in picked)
    return samples


def render_worksheet(
    samples: list[Sample],
    claims: list[dict[str, Any]],
    *,
    title: str,
    seed: int = 20261016,
) -> str:
    """产出可直接照着核对的 Markdown 工作表。"""
    counts = counts_by_stratum(claims)
    lines = [
        f"# 结论质量抽查工作表 · {title}",
        "",
        "> 本文件由 `parallax spotcheck` 生成，是**抽样清单**，不是结论。",
        "> 逐条到源码核对后，把 `判定` 一栏填成下列之一，然后据此统计精度。",
        "",
        "## 判定口径",
        "",
        "| 判定 | 含义 |",
        "|---|---|",
        "| `真缺陷` | 能在源码中指出具体触发路径 |",
        "| `误报` | 描述与代码不符，或属风格/主观偏好而非缺陷 |",
        "| `存疑` | 无法确认（证据不足、依赖运行时条件） |",
        "",
        "## 抽样方法",
        "",
        f"- 抽样自**完整 claim 集**（{len(claims)} 条），不是报告里渲染的那几十条",
        f"- 分层配额：{'、'.join(f'{k} {v} 条' for k, v in DEFAULT_PER_BUCKET.items())}",
        f"- 随机种子 `{seed}`：同输入同种子必得同一批样本，结果可复核",
        "- 某档不足配额时抽全部，并在下表注明实际条数",
        "",
        "## 全集分布（抽样是否覆盖得到的一手依据）",
        "",
        "| 档位 | 全集中条数 | 本次抽样条数 |",
        "| --- | ---: | ---: |",
    ]
    picked_counts = Counter(s.bucket for s in samples)
    for bucket in BUCKETS:
        lines.append(f"| `{bucket}` | {counts.get(bucket, 0)} | {picked_counts.get(bucket, 0)} |")
    for bucket in sorted(b for b in counts if b not in BUCKETS):
        lines.append(f"| `{bucket}` | {counts[bucket]} | — |")
    lines.append("")

    for bucket in BUCKETS:
        chosen = [s for s in samples if s.bucket == bucket]
        if not chosen:
            continue
        lines.append(f"## `{bucket}`（抽 {len(chosen)} / 共 {counts.get(bucket, 0)}）")
        lines.append("")
        lines.append("| # | 判定 | 缺陷类目 | 严重度 | 位置 | 主张 | 独立来源数 | claim_id |")
        lines.append("| ---: | --- | --- | --- | --- | --- | ---: | --- |")
        for index, sample in enumerate(chosen, start=1):
            claim = sample.claim
            lines.append(
                "| {i} |  | `{cls}` | {sev} | `{loc}` | {stmt} | {sources} | `{cid}` |".format(
                    i=index,
                    cls=claim.get("claim_type") or "?",
                    sev=claim.get("severity") or "?",
                    loc=claim.get("locator") or "?",
                    stmt=_escape(str(claim.get("statement") or "").strip()),
                    sources=len(claim.get("verified_by") or []),
                    cid=claim.get("claim_id") or "?",
                )
            )
        lines.append("")

    lines.extend(
        [
            "## 统计（核对完再填）",
            "",
            "| 档位 | 抽查条数 | 真缺陷 | 误报 | 存疑 | 精度（真缺陷 / 抽查条数） |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for bucket in BUCKETS:
        chosen = picked_counts.get(bucket, 0)
        if chosen:
            lines.append(f"| `{bucket}` | {chosen} | | | | |")
    lines.append("")
    lines.append("> **误报率要如实报告，无论高低。** 抽查的意义就在于给出这个数；")
    lines.append("> 如果它不好看，正确做法是写出来，而不是换一套抽样方式。")
    return "\n".join(lines)


def _escape(text: str) -> str:
    """Markdown 表格里不能出现裸竖线与换行。"""
    return text.replace("|", "\\|").replace("\n", " ")


def _label_for(claims_path: Path) -> str:
    """从文件名推一个短标签。

    `xxx.claims.json` 的 `stem` 是 `xxx.claims`，再切掉 `.claims` 才是运行名——
    否则生成的工作表叫 `a.claims-worksheet.md`，看起来像文件名被截断了。
    """
    stem = claims_path.stem
    return stem[: -len(".claims")] if stem.endswith(".claims") else stem


def write_outputs(
    claims_path: Path,
    out_dir: Path,
    *,
    title: str | None = None,
    per_bucket: dict[str, int] | None = None,
    seed: int = 20261016,
) -> tuple[Path, Path]:
    """生成工作表与样本 JSON，返回两者的路径。"""
    claims = load_claims(claims_path)
    samples = sample_claims(claims, per_bucket, seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    label = title or _label_for(claims_path)
    worksheet = out_dir / f"{label}-worksheet.md"
    worksheet.write_text(
        render_worksheet(samples, claims, title=label, seed=seed), encoding="utf-8"
    )

    payload = {
        "source": str(claims_path),
        "seed": seed,
        "worksheet": worksheet.name,
        "total_claims": len(claims),
        "strata": counts_by_stratum(claims),
        "samples": [
            {
                "bucket": sample.bucket,
                "claim_id": sample.claim.get("claim_id"),
                "claim": sample.claim,
            }
            for sample in samples
        ],
    }
    sample_path = out_dir / f"{label}-samples.json"
    sample_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return worksheet, sample_path
