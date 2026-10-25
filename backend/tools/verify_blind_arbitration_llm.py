"""结论剥离仲裁的**真实模型**对照实验。

离线版本（`verify_blind_arbitration.py`）用规则替身验证协议方向；本脚本把同一个
争议集交给真实模型，比较两种仲裁输入：

    statement_visible  把双方的自然语言结论一并给模型（LLMArbitrator 默认行为）
    redacted           只给立场、证据指针与引用片段（LLMArbitrator(redact_statements=True)）

判据来自 `eval/corpus/seed_java/ground_truth.json`：植入缺陷 → 期望 high_confidence，
已修复双胞胎与无信号位置 → 期望 pending。

用法（需要 backend/.env 中配置可用的模型）：
    .venv\\Scripts\\python.exe tools\\verify_blind_arbitration_llm.py --repeats 2 --out ..\\eval\\java-platform\\blind-arbitration-llm.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import verify_blind_arbitration as base

from parallax.config import load_settings
from parallax.core.ledger import LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.infra.arbitrator_llm import LLMArbitrator
from parallax.infra.llm_openai_compat import OpenAICompatClient


def _dispute_rows(samples: list[dict[str, Any]], *, dissenter: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position, sample in enumerate(samples):
        case = sample["case"]
        lines = sample["unit"].content.splitlines()
        quote = lines[case["span"][0] - 1].strip()
        majority_wrong = position % 2 == 0
        truth = Polarity.ASSERT if case["truth_defect"] else Polarity.DENY
        wrong = Polarity.DENY if truth == Polarity.ASSERT else Polarity.ASSERT
        majority = wrong if majority_wrong else truth
        dissenting = truth if majority_wrong else wrong
        polarities = [majority] * 4
        polarities[dissenter % 4] = dissenting
        claims = [
            base._claim(
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
        rows.append(
            {
                "case": case,
                "claims": claims,
                "group": LedgerGroup(
                    fingerprint=claims[0].fingerprint,
                    claim_ids=[claim.claim_id for claim in claims],
                    asserting_agents=[
                        c.extracted_by for c in claims if c.polarity == Polarity.ASSERT
                    ],
                    denying_agents=[c.extracted_by for c in claims if c.polarity == Polarity.DENY],
                ),
                "expected": (
                    ClaimStatus.HIGH_CONFIDENCE if case["truth_defect"] else ClaimStatus.PENDING
                ),
                "majority_wrong": majority_wrong,
                "majority_verdict": (
                    ClaimStatus.HIGH_CONFIDENCE
                    if majority == Polarity.ASSERT
                    else ClaimStatus.PENDING
                ),
            }
        )
    return rows


async def run_condition(
    client: OpenAICompatClient, rows: list[dict[str, Any]], *, redact: bool
) -> list[dict[str, Any]]:
    arbitrator = LLMArbitrator(client, redact_statements=redact)
    results: list[dict[str, Any]] = []
    for row in rows:
        started = time.perf_counter()
        verdict = await arbitrator.arbitrate(row["group"], row["claims"])
        elapsed = round(time.perf_counter() - started, 3)
        results.append(
            {
                "case_id": row["case"]["case_id"],
                "group": row["case"]["group"],
                "claim_type": row["case"]["claim_type"],
                "truth_defect": row["case"]["truth_defect"],
                "majority_wrong": row["majority_wrong"],
                "expected": row["expected"].value,
                "verdict": verdict.value,
                "followed_majority": verdict == row["majority_verdict"],
                "correct": verdict == row["expected"],
                "failed": verdict == ClaimStatus.DISPUTED,
                "seconds": elapsed,
            }
        )
    return results


def summarise(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    total = len(rows)
    failed = sum(1 for row in rows if row["failed"])
    decided = [row for row in rows if not row["failed"]]
    majority_wrong = [row for row in rows if row["majority_wrong"] and not row["failed"]]
    return {
        "condition": condition,
        "cases": total,
        "failed_calls": failed,
        "accuracy": round(sum(row["correct"] for row in rows) / total, 4),
        "decided_accuracy": round(sum(row["correct"] for row in decided) / max(1, len(decided)), 4),
        "wrong_majority_followed_rate": round(
            sum(1 for row in majority_wrong if row["followed_majority"])
            / max(1, len(majority_wrong)),
            4,
        ),
        "minority_recovered_rate": round(
            sum(1 for row in majority_wrong if row["correct"] and row["expected"] == row["verdict"])
            / max(1, len(majority_wrong)),
            4,
        ),
        "mean_seconds": round(sum(row["seconds"] for row in rows) / total, 3) if total else 0.0,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 个场景（调试用）")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.is_llm_configured():
        print("未配置模型 API Key，无法运行真实模型实验")
        return 2

    samples = base.build_cases()
    if args.limit:
        samples = samples[: args.limit]

    client = OpenAICompatClient(settings)
    started = time.perf_counter()
    conditions: dict[str, list[dict[str, Any]]] = {"statement_visible": [], "redacted": []}
    try:
        for repeat in range(args.repeats):
            for name, redact in (("statement_visible", False), ("redacted", True)):
                rows = _dispute_rows(samples, dissenter=repeat)
                results = await run_condition(client, rows, redact=redact)
                for item in results:
                    item["repeat"] = repeat
                conditions[name].extend(results)
    finally:
        usage = client.usage.model_dump() if getattr(client, "usage", None) is not None else {}
        await client.aclose()
    elapsed = round(time.perf_counter() - started, 2)

    payload = {
        "experiment": "blind-arbitration-llm",
        "date": "2026-10-25",
        "model": settings.llm_model,
        "base_url_host": settings.llm_base_url.split("//")[-1].split("/")[0],
        "corpus": "eval/corpus/seed_java",
        "design": {
            "cases": len(samples),
            "repeats": args.repeats,
            "dissenter_position": "repeat % 4",
            "conditions": {
                "statement_visible": "把双方自然语言结论发给模型",
                "redacted": "只给立场、证据指针与引用片段，不发结论",
            },
        },
        "summary": [
            summarise(conditions["statement_visible"], "statement_visible"),
            summarise(conditions["redacted"], "redacted"),
        ],
        "rows": conditions,
        "wall_seconds": elapsed,
        "usage": usage,
        "limitations": [
            "12 个场景（4 植入缺陷 + 8 对照）规模很小，只作方向性证据，不作统计显著性主张。",
            "同一端点的单模型自审：模型既可能是提结论的一方，也可能是仲裁方，独立性受此限制。",
            "模型别名不构成官方型号证明；失败调用记为 disputed 并单独报告。",
            "ground truth 只有 4 个缺陷，缺陷类覆盖为 business_invariant/atomicity/concurrency/error_handling 各一例。",
        ],
    }

    for item in payload["summary"]:
        print(
            f"{item['condition']:<18} acc={item['accuracy']:.2f} "
            f"decided={item['decided_accuracy']:.2f} "
            f"minority_saved={item['minority_recovered_rate']:.2f} "
            f"majority_followed={item['wrong_majority_followed_rate']:.2f} "
            f"failed={item['failed_calls']} mean={item['mean_seconds']}s"
        )
    print(f"wall={elapsed}s")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
