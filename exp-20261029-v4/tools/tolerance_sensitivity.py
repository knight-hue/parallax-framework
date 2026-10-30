"""容差敏感度：把所有历史产物的召回按 25 / 10 / 5 / 0 行分别算一遍。

## 为什么必须做

`score.py` 的匹配口径是「同文件 + 行距 ≤ 25 + `stance=defect`」。
25 行是**宽松上界**：缺陷密集的文件里，一条「附近另一个问题」会被计成命中。

E-9 已实测到这个偏差：S7-hard 上同一批运行，25 行口径给 5/5，
逐条人工裁定只有 3/5，**高估 2 条**。

单给一个宽松数字站不住脚；给一条曲线则可以说清楚
「结论在哪个容差下成立、从哪个容差开始塌」。

## 用法

    python tools/tolerance_sensitivity.py
    python tools/tolerance_sensitivity.py --tolerances 25,15,10,5,3,0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score import score  # noqa: E402

CORPORA = ("p1-subsample", "p0-slices")
# 只收录口径干净的产物目录（p3-e1 是 flash 时代的废数据，显式排除）
RUNS = ("p4-chat", "p5-e3", "p5-e3b", "p6-single", "p6-single-context", "p7-hard")


def load_truth_index() -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for corpus in CORPORA:
        for gt in (EXP / corpus).glob("*/ground_truth.json"):
            data = json.loads(gt.read_text(encoding="utf-8"))
            task_id = data.get("task_id") or gt.parent.name
            index[task_id] = data["defects"]
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tolerances", default="25,10,5,0", help="逗号分隔的行距容差"
    )
    args = parser.parse_args()
    tolerances = [int(x) for x in args.tolerances.split(",")]

    truth = load_truth_index()
    # (run, arm) -> {task_id: {tol: hits}}
    table: dict[tuple[str, str], dict[str, dict[int, dict]]] = {}
    unknown: list[str] = []

    for run in RUNS:
        for claims_file in sorted((EXP / run).rglob("*.claims.json")):
            stem = claims_file.name[: -len(".claims.json")]
            task_id, _, arm = stem.partition("__")
            if task_id not in truth:
                unknown.append(f"{run}/{stem}")
                continue
            claims = json.loads(claims_file.read_text(encoding="utf-8"))
            if isinstance(claims, dict):
                claims = claims.get("claims", [])
            per_tol = {
                tol: score(claims, truth[task_id], tolerance=tol) for tol in tolerances
            }
            table.setdefault((run, arm), {})[task_id] = per_tol

    if unknown:
        print("⚠ 找不到真值、已跳过的产物：")
        for item in unknown:
            print(f"    {item}")

    print()
    header = "目录".ljust(20) + "臂".ljust(26) + "任务数".rjust(6)
    for tol in tolerances:
        header += f"  ≤{tol:<3d}".rjust(8)
    print(header)
    print("-" * len(header))

    aggregated: dict[str, dict[int, tuple[int, int]]] = {}
    for (run, arm), tasks in sorted(table.items()):
        row = f"{run:<20}{arm:<26}{len(tasks):>6}"
        for tol in tolerances:
            hits = sum(v[tol]["hits"] for v in tasks.values())
            total = sum(v[tol]["defects_total"] for v in tasks.values())
            row += f"  {hits}/{total}".rjust(8)
            agg = aggregated.setdefault(arm, {})
            oh, ot = agg.get(tol, (0, 0))
            agg[tol] = (oh + hits, ot + total)
        print(row)

    print("\n按臂汇总（跨全部切片）：")
    print("臂".ljust(28) + "".join(f"  ≤{tol}".rjust(12) for tol in tolerances))
    for arm, agg in sorted(aggregated.items()):
        line = arm.ljust(28)
        for tol in tolerances:
            hits, total = agg[tol]
            rate = hits / total if total else 0.0
            line += f"  {hits}/{total} {rate:.0%}".rjust(12)
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
