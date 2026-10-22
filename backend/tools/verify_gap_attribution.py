"""覆盖缺口归因的验证实验。

三部分：

A. 估计量有效性（模拟）
   已知总体 N=40，k 个 Reader 以检出概率 p 独立抽样。检验 Chapman 中位数估计
   能否把 N 估回来，以及"无重捕时不发数字"的约束是否生效。

B. 归因判定（构造场景）
   分区缺口 / 读者漏检 / 干净证据三种场景，检查归因是否给出对应结论；
   干净证据**不应该**被判成 reader_miss——它应该诚实地停在 unresolved。

C. 真实语料形状（seed_java）
   4 个植入缺陷 + 4 个已修复双胞胎，3 个 Reader，看归因在真实文件集合上的输出。

用法：
    .venv\\Scripts\\python.exe tools\\verify_gap_attribution.py --out ..\\eval\\java-platform\\gap-attribution.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from parallax.core.gap_attribution import attribute_gaps, estimate_capture
from parallax.domain.models import Claim, SourceRef

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "eval" / "corpus" / "seed_java"
CLASSES = ("Account", "ReportExporter", "TokenBucket", "ConfigLoader")


def _claim(fingerprint: str, reader: str, evidence_id: str) -> Claim:
    return Claim(
        claim_id=f"{fingerprint}:{reader}",
        fingerprint=fingerprint,
        statement=f"{fingerprint} 判定",
        claim_type="generic",
        extracted_by=reader,
        source_refs=[SourceRef(evidence_id=evidence_id, adapter="sim", locator=evidence_id)],
    )


def _sample_population(
    population: list[str], readers: list[str], probability: float, rng: random.Random
) -> dict[str, set[str]]:
    return {
        reader: {item for item in population if rng.random() < probability} for reader in readers
    }


def part_a(replications: int = 200) -> list[dict[str, Any]]:
    """估计量有效性。"""
    population = [f"defect-{index:02d}" for index in range(40)]
    results: list[dict[str, Any]] = []
    for probability in (0.4, 0.6, 0.8):
        rng = random.Random(1_000 + int(probability * 100))
        estimates: list[float] = []
        observed: list[int] = []
        estimable = 0
        within = 0
        for _ in range(replications):
            samples = _sample_population(population, ["r1", "r2", "r3"], probability, rng)
            estimate = estimate_capture(samples)
            observed.append(estimate.observed)
            if estimate.estimated_total is None:
                continue
            estimable += 1
            estimates.append(estimate.estimated_total)
            if abs(estimate.estimated_total - len(population)) / len(population) <= 0.2:
                within += 1
        mean_estimate = sum(estimates) / len(estimates) if estimates else None
        results.append(
            {
                "detection_probability": probability,
                "population": len(population),
                "replications": replications,
                "estimable_rate": round(estimable / replications, 4),
                "mean_observed": round(sum(observed) / len(observed), 3),
                "mean_estimate": round(mean_estimate, 3) if mean_estimate else None,
                "relative_bias": round((mean_estimate - len(population)) / len(population), 4)
                if mean_estimate
                else None,
                "within_20pct_rate": round(within / max(1, estimable), 4),
            }
        )
    return results


def part_b() -> list[dict[str, Any]]:
    """归因判定：三种构造场景。"""
    scenarios: list[dict[str, Any]] = []

    # 场景 1：分区缺口——每条证据只有 1-2 个 Reader 看过（min_support=3）。
    assignments = {
        "r1": ["e1", "e2", "e3", "e4"],
        "r2": ["e3", "e4", "e5", "e6"],
        "r3": ["e5", "e6"],
    }
    claims = [_claim("e3#x@v1", "r1", "e3"), _claim("e3#x@v1", "r2", "e3")]
    report = attribute_gaps(
        assignments=assignments,
        claims=claims,
        groups={f"e{i}": f"module-{i}" for i in range(1, 7)},
        min_support=3,
    )
    scenarios.append(
        {
            "scenario": "partition_gap",
            "expected": "partition_gap",
            "by_kind": report.by_kind,
            "actionable_groups": report.actionable_groups,
            "detection_probability": report.run_estimate.detection_probability,
        }
    )

    # 场景 2：读者漏检——每条证据都被 3 个 Reader 看过，其中两条真实缺陷无人报出。
    population = ["s2#a@v1", "s2#b@v1", "s2#c@v1", "s2#d@v1", "s2#e@v1"]
    rng = random.Random(7)
    samples = _sample_population(population, ["r1", "r2", "r3"], 0.8, rng)
    assignments = {
        "r1": ["s1", "s2", "s3", "s4", "s5", "s6"],
        "r2": ["s1", "s2", "s3", "s4", "s5", "s6"],
        "r3": ["s1", "s2", "s3", "s4", "s5", "s6"],
    }
    claims = []
    for reader, fingerprints in samples.items():
        for fingerprint in sorted(fingerprints):
            claims.append(_claim(fingerprint, reader, "s1"))
    # s5 / s6 是"真实有缺陷但全员没报出"的证据：它们零检出。
    report = attribute_gaps(
        assignments=assignments,
        claims=claims,
        groups={f"s{i}": f"module-{i}" for i in range(1, 7)},
        min_support=3,
    )
    scenarios.append(
        {
            "scenario": "reader_miss",
            "expected": "reader_miss on zero-detection evidence",
            "by_kind": report.by_kind,
            "detection_probability": report.run_estimate.detection_probability,
            "zero_detection_kinds": {
                item.evidence_id: item.kind for item in report.items if item.claims == 0
            },
        }
    )

    # 场景 3：干净证据——没有任何 claim。此时既无重捕也无法估 p̄，必须停在 unresolved。
    assignments = {f"r{i}": [f"c{j}" for j in range(1, 6)] for i in (1, 2, 3)}
    report = attribute_gaps(
        assignments=assignments,
        claims=[],
        groups={f"c{j}": f"module-{j}" for j in range(1, 6)},
        min_support=3,
    )
    scenarios.append(
        {
            "scenario": "clean_evidence",
            "expected": "unresolved (干净与集体漏检在无标定时不可区分)",
            "by_kind": report.by_kind,
            "detection_probability": report.run_estimate.detection_probability,
        }
    )
    return scenarios


def part_c() -> dict[str, Any]:
    """真实语料形状：4 个缺陷文件 + 4 个修复版，3 个 Reader，p=0.7。"""
    truth = json.loads((CORPUS / "ground_truth.json").read_text(encoding="utf-8"))
    defect_files = {Path(item["file"]).name: item["defect_class"] for item in truth["defects"]}
    evidence = [f"src/main/java/dev/parallax/corpus/java/{name}.java" for name in CLASSES] + [
        f"reference/{name}.java" for name in CLASSES
    ]
    groups = {path: Path(path).stem for path in evidence}

    rng = random.Random(11)
    assignments = {f"r{i}": list(evidence) for i in (1, 2, 3)}
    claims: list[Claim] = []
    for path in evidence:
        name = Path(path).name
        if not path.startswith("src/"):
            continue  # 修复版没有缺陷，检出为空
        defect_class = defect_files.get(name)
        if defect_class is None:
            continue
        for reader in ("r1", "r2", "r3"):
            if rng.random() < 0.7:
                claims.append(_claim(f"{path}#{defect_class}@v1", reader, path))

    report = attribute_gaps(assignments=assignments, claims=claims, groups=groups, min_support=2)
    return {
        "evidence": len(evidence),
        "claims": len(claims),
        "by_kind": report.by_kind,
        "detection_probability": report.run_estimate.detection_probability,
        "estimated_total": report.run_estimate.estimated_total,
        "items": [
            {
                "evidence_id": item.evidence_id,
                "kgroup": item.group,
                "readers": item.readers,
                "claims": item.claims,
                "kind": item.kind,
            }
            for item in report.items
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = {
        "experiment": "gap-attribution",
        "date": "2026-10-22",
        "corpus": "eval/corpus/seed_java",
        "part_a_estimator": part_a(),
        "part_b_attribution": part_b(),
        "part_c_corpus": part_c(),
        "limitations": [
            "A/B 部分是模拟：Reader 被建模为独立同分布的伯努利采样，真实模型同源、证据难易不均，会让 Chapman 的独立性假设失效。",
            "Chapman 只在有重捕时给数；无重捕一律返回 None，因此本实验不报告「漏检 100%」这类伪精度结论。",
            "C 部分的检出也是模拟（p=0.7）；它验证的是机制在真实文件集合上的接线，不是该语料上的真实召回率。",
            "归因阈值 miss_threshold=0.5 是默认值，未做敏感性扫描；判为 unresolved 的证据应定向补检或交还人工。",
        ],
    }

    print(json.dumps(payload["part_a_estimator"], ensure_ascii=False, indent=2))
    print(json.dumps(payload["part_b_attribution"], ensure_ascii=False, indent=2))
    print(json.dumps(payload["part_c_corpus"]["by_kind"], ensure_ascii=False))

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
