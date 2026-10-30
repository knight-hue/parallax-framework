"""E4：按「最近 claim」口径压成一行一条，供人工判定真假。

⚠️ 为什么要人工判：召回靠「路径 + 行号 ±25」匹配，而植入缺陷在文件里是密集分布的。
同一文件里两条缺陷相距 10 行时，模型报其中一条，另一条也会被算成命中。
这不是匹配 bug，是「接近 ≠ 说的是同一件事」。只能人看。
"""

from __future__ import annotations

import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP / "p4-chat"
GT_ROOT = EXP / "p1-subsample"

CENTRAL = "no_peers_all_evidence"
DISPERSED = "blind_no_coverage"
TOLERANCE = 25


def norm(path: str) -> str:
    return (path or "").split(":")[0].replace("\\", "/").strip().lstrip("./")


def line_of(claim: dict) -> int:
    value = claim.get("line_start")
    return value if isinstance(value, int) else -1


def closest_claim(claims: list[dict], defect: dict) -> dict | None:
    candidates = [
        c
        for c in claims
        if norm(c.get("locator")) == norm(defect["file"])
        and abs(line_of(c) - defect["line_start"]) <= TOLERANCE
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs(line_of(c) - defect["line_start"]))


def short(text: str, width: int = 46) -> str:
    return (text or "").replace("\n", " ")[:width]


def main() -> int:
    for shard in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        gt_path = GT_ROOT / shard.name / "ground_truth.json"
        if not gt_path.exists():
            continue
        defects = json.loads(gt_path.read_text(encoding="utf-8"))["defects"]
        print(f"\n### {shard.name}")
        for arm in (CENTRAL, DISPERSED):
            path = next(shard.glob(f"*__{arm}.claims.json"), None)
            if path is None:
                continue
            claims = json.loads(path.read_text(encoding="utf-8"))
            metrics = json.loads((shard / "metrics.json").read_text(encoding="utf-8"))
            arm_metrics = next(a for a in metrics["arms"] if a["arm"] == arm)
            hit_ids = {d["defect_id"] for d in arm_metrics["defects"] if d["found_by"]}

            print(f"\n  [{arm}] 框架判为命中 {len(hit_ids)}/{len(defects)}")
            for defect in defects:
                mark = "HIT " if defect["id"] in hit_ids else "    "
                claim = closest_claim(claims, defect)
                claim_text = short(claim.get("title") or claim.get("statement") or "") if claim else "—"
                print(f"    {mark}{defect['id']:30s} | 植入：{short(defect['title'], 30):30s} | 最近claim：{claim_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
