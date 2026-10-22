"""结论剥离仲裁的对照实验（离线、确定性、可复算）。

## 实验问题

当争议的两方人数是 3:1 时，仲裁者读到的是**结论**还是**观察**，会不会改变裁决？

- `stickiness = 0.0`：结论完全剥离，仲裁者只按证据信号裁决（`BlindArbitrator`）；
- `stickiness = 1.0`：完全转发结论，按人数裁决（`RelayArbitrator`，即
  arXiv 2609.07680 描述的失败模式的确定性替身）；
- 中间值：读了结论但仍会去核对证据的过渡带。

## 场景构成（12 个）

| 组 | 数量 | 含义 |
| --- | --- | --- |
| 植入缺陷 | 4 | `ground_truth.json` 的真实缺陷 |
| 已修复双胞胎 | 4 | `reference/` 中同一个方法的修复版，带边界/同步/抛出等防护 |
| 无信号位置 | 4 | 结构上既无坏味道也无防护，正确行为是升级人工而不是猜 |

每个场景 4 条 claim，极性 3:1，相邻场景交替"多数派是对/错"，
因此多数派基线在期望上不占便宜也不吃亏。

## 指标

- `strict_accuracy`：裁决与真值一致（缺陷 → high_confidence，无缺陷 → pending）；
- `escalation_rate`：保留争议（disputed），即交还人工；
- `wrong_majority_upheld_rate`：多数派错时，仲裁者仍维持多数派的比例（越低越好）；
- `correct_minority_recovered_rate`：多数派错时，正确少数被救回的比例（越高越好）。

用法：
    .venv\\Scripts\\python.exe tools\\verify_blind_arbitration.py --out ..\\eval\\java-platform\\blind-arbitration.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from parallax.core.arbitration import StickyArbitrator
from parallax.core.ledger import LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import Claim, EvidenceUnit, SourceRef

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "eval" / "corpus" / "seed_java"
CLASSES = ("Account", "ReportExporter", "TokenBucket", "ConfigLoader")

_METHOD = re.compile(
    r"^\s{4}(?:public|private|protected|static|final|synchronized|\s)*[\w<>\[\], ]+\s+(\w+)\s*\("
)

# 无信号位置：结构上既没有坏味道，也没有防护。正确行为是升级人工。
NO_SIGNAL = (
    ("reference/Account.java", "balanceOf", "business_invariant"),
    ("reference/ConfigLoader.java", "ConfigLoader", "error_handling"),
    ("reference/TokenBucket.java", "availableTokens", "concurrency"),
    ("reference/TokenBucket.java", "TokenBucket", "concurrency"),
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _method_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """方法名 → (起始行, 结束行)，1 基，按大括号配对。"""
    ranges: dict[str, tuple[int, int]] = {}
    for index, line in enumerate(lines):
        match = _METHOD.match(line)
        if match is None:
            continue
        name = match.group(1)
        if name in {"if", "for", "while", "switch", "catch", "return", "new"}:
            continue
        depth = 0
        started = False
        for cursor in range(index, len(lines)):
            depth += lines[cursor].count("{") - lines[cursor].count("}")
            if "{" in lines[cursor]:
                started = True
            if started and depth <= 0:
                ranges.setdefault(name, (index + 1, cursor + 1))
                break
    return ranges


def _unit(rel: str, text: str) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=rel,
        adapter="seed-java",
        locator=rel,
        content=text,
        content_hash=_sha(text),
        group=Path(rel).stem,
    )


def _claim(
    *,
    rel: str,
    span: tuple[int, int],
    claim_type: str,
    polarity: Polarity,
    agent: str,
    index: int,
    quote: str,
) -> Claim:
    fingerprint = f"{rel}#{claim_type}@v1"
    stance = "存在该缺陷" if polarity == Polarity.ASSERT else "不存在该缺陷"
    return Claim(
        claim_id=f"{fingerprint}:{agent}",
        fingerprint=fingerprint,
        statement=f"[{claim_type}] {rel}:{span[0]}-{span[1]} {stance}（第 {index} 号读者）",
        polarity=polarity,
        claim_type=claim_type,
        extracted_by=agent,
        source_refs=[
            SourceRef(
                evidence_id=rel,
                adapter="seed-java",
                locator=f"{rel}:{span[0]}-{span[1]}",
                quote=quote,
            )
        ],
        reputation_at_extraction=0.5,
    )


def build_cases() -> list[dict[str, Any]]:
    truth = json.loads((CORPUS / "ground_truth.json").read_text(encoding="utf-8"))
    units: dict[str, EvidenceUnit] = {}
    ranges: dict[str, dict[str, tuple[int, int]]] = {}
    for rel in [f"src/main/java/dev/parallax/corpus/java/{name}.java" for name in CLASSES] + [
        f"reference/{name}.java" for name in CLASSES
    ]:
        text = (CORPUS / rel).read_text(encoding="utf-8")
        units[rel] = _unit(rel, text)
        ranges[rel] = _method_ranges(text.splitlines())

    cases: list[dict[str, Any]] = []
    planted_method: dict[str, str] = {}
    for defect in truth["defects"]:
        rel = defect["file"].replace("\\", "/")
        span = next(
            (r for r in ranges[rel].values() if r[0] <= defect["line_start"] <= r[1]),
            (defect["line_start"], defect["line_end"]),
        )
        planted_method[Path(rel).stem] = next(
            (name for name, r in ranges[rel].items() if r == span), ""
        )
        cases.append(
            {
                "case_id": defect["id"],
                "group": "planted",
                "rel": rel,
                "span": span,
                "claim_type": defect["defect_class"],
                "truth_defect": True,
            }
        )

    for name in CLASSES:
        rel = f"reference/{name}.java"
        method = planted_method.get(name, "")
        target = ranges[rel].get(method, (1, 1))
        cases.append(
            {
                "case_id": f"R-{name}",
                "group": "guarded-twin",
                "rel": rel,
                "span": target,
                "claim_type": next(
                    c["claim_type"] for c in cases if c["rel"].endswith(f"{name}.java")
                ),
                "truth_defect": False,
            }
        )

    for rel, method, claim_type in NO_SIGNAL:
        cases.append(
            {
                "case_id": f"N-{Path(rel).stem}-{method}",
                "group": "no-signal",
                "rel": rel,
                "span": ranges[rel].get(method, (1, 1)),
                "claim_type": claim_type,
                "truth_defect": False,
            }
        )
    return [{"case": case, "unit": units[case["rel"]]} for case in cases]


async def run(samples: list[dict[str, Any]], stickiness: float, seed: int) -> dict[str, Any]:
    arbitrator = StickyArbitrator(stickiness=stickiness, seed=seed)
    evidence = {sample["unit"].evidence_id: sample["unit"] for sample in samples}
    arbitrator.bind_evidence(evidence)

    rows: list[dict[str, Any]] = []
    for position, sample in enumerate(samples):
        case = sample["case"]
        lines = sample["unit"].content.splitlines()
        quote = lines[case["span"][0] - 1].strip()
        # 相邻场景交替：偶数位多数派错，奇数位多数派对。
        majority_wrong = position % 2 == 0
        truth_polarity = Polarity.ASSERT if case["truth_defect"] else Polarity.DENY
        minority_polarity = Polarity.DENY if truth_polarity == Polarity.ASSERT else Polarity.ASSERT
        # 多数派要么是错的那边（陷阱），要么是对的那边；第 4 条永远站相反立场。
        majority_polarity = minority_polarity if majority_wrong else truth_polarity
        dissenter_polarity = truth_polarity if majority_wrong else minority_polarity
        expected = ClaimStatus.HIGH_CONFIDENCE if case["truth_defect"] else ClaimStatus.PENDING
        majority_verdict = (
            ClaimStatus.HIGH_CONFIDENCE
            if majority_polarity == Polarity.ASSERT
            else ClaimStatus.PENDING
        )
        # 异见者出现在哪个位置不应影响结论：四个位置各跑一次，把样本量乘 4。
        for dissenter in range(4):
            polarities = [majority_polarity] * 4
            polarities[dissenter] = dissenter_polarity
            claims = [
                _claim(
                    rel=case["rel"],
                    span=case["span"],
                    claim_type=case["claim_type"],
                    polarity=polarity,
                    agent=f"r{index + 1}",
                    index=index + 1,
                    quote=quote,
                )
                for index, polarity in enumerate(polarities)
            ]
            group = LedgerGroup(
                fingerprint=claims[0].fingerprint,
                claim_ids=[claim.claim_id for claim in claims],
                asserting_agents=[
                    claim.extracted_by for claim in claims if claim.polarity == Polarity.ASSERT
                ],
                denying_agents=[
                    claim.extracted_by for claim in claims if claim.polarity == Polarity.DENY
                ],
            )
            verdict = await arbitrator.arbitrate(group, claims)
            rows.append(
                {
                    "case_id": case["case_id"],
                    "group": case["group"],
                    "claim_type": case["claim_type"],
                    "truth_defect": case["truth_defect"],
                    "majority_wrong": majority_wrong,
                    "dissenter": dissenter + 1,
                    "expected": expected.value,
                    "verdict": verdict.value,
                    "strict_correct": verdict == expected,
                    "escalated": verdict == ClaimStatus.DISPUTED,
                    "wrong_decision": verdict not in {expected, ClaimStatus.DISPUTED},
                    "followed_majority": verdict == majority_verdict,
                    "recovered_minority": majority_wrong and verdict == expected,
                    "signals": [claim.metadata.get("evidence_signal", "-") for claim in claims],
                }
            )
    return {"stickiness": stickiness, "rows": rows}


def summarise(run_result: dict[str, Any]) -> dict[str, Any]:
    rows = run_result["rows"]
    total = len(rows)
    majority_wrong = [row for row in rows if row["majority_wrong"]]
    decided = [row for row in rows if not row["escalated"]]
    return {
        "stickiness": run_result["stickiness"],
        "cases": total,
        "wrong_decision_rate": round(sum(row["wrong_decision"] for row in rows) / total, 4),
        "decisive_accuracy": round(
            sum(row["strict_correct"] for row in decided) / max(1, len(decided)), 4
        ),
        "escalation_rate": round(sum(row["escalated"] for row in rows) / total, 4),
        "wrong_majority_upheld_rate": round(
            sum(row["followed_majority"] for row in majority_wrong) / max(1, len(majority_wrong)), 4
        ),
        "correct_minority_recovered_rate": round(
            sum(row["recovered_minority"] for row in majority_wrong) / max(1, len(majority_wrong)),
            4,
        ),
        "by_group": {
            group: {
                "cases": len(rows_in_group),
                "wrong_decision_rate": round(
                    sum(row["wrong_decision"] for row in rows_in_group) / len(rows_in_group), 4
                ),
                "escalation_rate": round(
                    sum(row["escalated"] for row in rows_in_group) / len(rows_in_group), 4
                ),
            }
            for group in ("planted", "guarded-twin", "no-signal")
            if (rows_in_group := [row for row in rows if row["group"] == group])
        },
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sweep", type=float, nargs="+", default=[0.0, 0.25, 0.5, 0.75, 1.0])
    args = parser.parse_args()

    samples = build_cases()
    runs = [await run(samples, stickiness, args.seed) for stickiness in args.sweep]
    summary = [summarise(result) for result in runs]

    print(
        f"{'stickiness':>10} {'wrong_dec':>10} {'decisive_acc':>13} {'escalated':>10} {'majority_upheld':>16} {'minority_saved':>15}"
    )
    for item in summary:
        print(
            f"{item['stickiness']:>10.2f} {item['wrong_decision_rate']:>10.2f} "
            f"{item['decisive_accuracy']:>13.2f} {item['escalation_rate']:>10.2f} "
            f"{item['wrong_majority_upheld_rate']:>16.2f} "
            f"{item['correct_minority_recovered_rate']:>15.2f}"
        )

    payload = {
        "experiment": "blind-arbitration-ab",
        "date": "2026-10-22",
        "corpus": "eval/corpus/seed_java",
        "corpus_digests": sorted({sample["unit"].content_hash for sample in samples}),
        "seed": args.seed,
        "design": {
            "cases": len(samples),
            "claims_per_case": 4,
            "dissenter_positions": 4,
            "disputes": len(runs[0]["rows"]),
            "polarity_split": "3:1, majority correctness alternates by case, dissenter rotates over all 4 seats",
            "arms": {
                "stickiness=0.0": "结论剥离：BlindArbitrator 只按证据信号裁决",
                "0<stickiness<1": "结论可见但会核对证据的过渡带",
                "stickiness=1.0": "结论中继：RelayArbitrator 按人数裁决",
            },
        },
        "summary": summary,
        "rows_by_stickiness": {f"{result['stickiness']:.2f}": result["rows"] for result in runs},
        "limitations": [
            "离线确定性实验：仲裁行为由规则模型定义，不是真实 LLM 的实测；认知层面的结论来自 arXiv 2609.07680，本实验只验证协议层的方向与幅度。",
            "语料是 4 个植入缺陷 + 8 个对照，规模小；结论是方向性的，不是统计显著的生产结论。",
            "信号谓词是通用 Java 结构性坏味道（减法直写、先写后校验、截断后无条件推进时间基准、吞异常返回字面量），不是对该语料标记的硬编码，但作者在编写时知道缺陷分类。",
            "3:1 的人数分布是刻意的从众陷阱；真实场景的比例会变化，本实验不代表一般情形下的准确率。",
            "无信号位置的正确行为是升级人工；结论中继不会升级任何争议，因此它在这些位置上只能猜——命中一半来自硬币，不是能力。",
        ],
    }

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
