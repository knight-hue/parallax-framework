"""独立性准入闸门的演示与验证（离线、确定性、无需模型）。

扫描冗余旋钮 redundancy=1..3，在固定证据集上算出：
- 有效独立通道数、归一化独立性、证据重叠率；
- 三种闸门模式下的判定（off / observe / enforce）。

它回答的问题是：**同一个指标，从"只记录"变成"阻断"之后，系统行为是否真的改变。**
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from parallax.core.admission import IndependenceGate, suggest_remedy
from parallax.core.independence import build_independence_profile
from parallax.core.partitioning import BlindPartitioner
from parallax.domain.models import Claim, EvidenceUnit, SourceRef


def _evidence(count: int = 8) -> list[EvidenceUnit]:
    return [
        EvidenceUnit(
            evidence_id=f"mod{index // 2}/file{index}.py",
            adapter="demo",
            locator=f"mod{index // 2}/file{index}.py",
            content=f"# file {index}\n",
            group=f"mod{index // 2}",
        )
        for index in range(count)
    ]


def _claims(assignments: dict[str, list[str]]) -> list[Claim]:
    """每个 Reader 对自己读过的每份证据都报一条指纹——完美检出的对照组。"""
    claims: list[Claim] = []
    for reader, evidence_ids in assignments.items():
        for evidence_id in evidence_ids:
            fingerprint = f"{evidence_id}#generic@0"
            claims.append(
                Claim(
                    claim_id=f"{fingerprint}:{reader}",
                    fingerprint=fingerprint,
                    statement="样本结论",
                    claim_type="generic",
                    extracted_by=reader,
                    source_refs=[
                        SourceRef(evidence_id=evidence_id, adapter="demo", locator=evidence_id)
                    ],
                )
            )
    return claims


def sweep(threshold: float = 2.6, attempts: int = 0) -> list[dict]:
    rows: list[dict] = []
    evidence = _evidence()
    for redundancy in (1, 2, 3):
        partitioner = BlindPartitioner(n_readers=3, redundancy=redundancy, seed=0)
        partitions = partitioner.partition(evidence, round_index=0)
        assignments = {p.reader_id: p.evidence_ids for p in partitions if p.units}
        claims = _claims(assignments)
        profile = build_independence_profile(claims, assignments, evidence=evidence)
        decisions = {}
        for mode in ("off", "observe", "enforce"):
            gate = IndependenceGate(
                mode=mode,
                min_effective_channels=threshold,
                max_attempts=1,
            )
            decisions[mode] = gate.evaluate(profile, attempts=attempts).action
        remedy, note = suggest_remedy(
            profile,
            overlap_budget=0.5,
            n_readers=len(assignments),
            redundancy=redundancy,
        )
        rows.append(
            {
                "redundancy": redundancy,
                "readers": len(assignments),
                "evidence_units": len(evidence),
                "effective_channels": round(profile.effective_channel_count, 4),
                "normalized_independence": round(profile.normalized_independence, 4),
                "evidence_overlap_rate": round(profile.evidence_overlap_rate, 4),
                "remedy": remedy,
                "remedy_note": note,
                "decisions": decisions,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = {
        "experiment": "independence-gate",
        "date": "2026-10-22",
        "design": {
            "evidence": "8 units / 4 groups, 3 readers",
            "threshold": {"min_effective_channels": 2.6},
            "sweep": "redundancy 1..3",
            "attempts": 0,
        },
        "sweep_at_zero_attempts": sweep(attempts=0),
        "sweep_after_one_attempt": sweep(attempts=1),
        "limitations": [
            "离线合成证据，Reader 是完美检出：本实验验证的是「指标→判定→处置」的接线与方向，不是真实模型的检出率。",
            "有效通道数是基于证据分区 Jaccard 相关矩阵的参与率指标，不是因果意义上的独立通道数；它只回答「输入有多重叠」。",
            "enforce 的重分区只提高 redundancy，不改变 Reader 身份之外的其它因素；若冗余已封顶，闸门直接降级而不空转。",
            "门槛 2.6 是演示值；生产阈值应由目标误报率反推，本实验未做该标定。",
        ],
    }

    for row in payload["sweep_at_zero_attempts"]:
        print(
            f"redundancy={row['redundancy']}  effective={row['effective_channels']:.3f}  "
            f"normalized={row['normalized_independence']:.3f}  overlap={row['evidence_overlap_rate']:.3f}  "
            f"remedy={row['remedy']}  decisions={row['decisions']}"
        )
    print("--- attempts=1 ---")
    for row in payload["sweep_after_one_attempt"]:
        print(f"redundancy={row['redundancy']}  decisions={row['decisions']}")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
