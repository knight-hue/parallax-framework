"""零成本：从既有产物里算「顺序 vs 并发」的延迟差。

## 为什么这个不用再花钱

`sharded_shared` 走的是 `_run_shared`——**顺序**执行，后一个 Reader 必须等前一个；
`sharded_blind` 走 `asyncio.gather`——**并发**执行。
两者召回无差（隔离 3 胜 2 平），但墙钟时间应当有明显差别。

每个臂的 `elapsed_s` 早已写在 `metrics.json` 里，直接聚合即可，**不需要任何模型调用**。

这是多智能体唯一还没被否定的卖点：**同样的质量，更短的等待。**
"""

from __future__ import annotations

import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOTS = [EXP / "p5-e3b", EXP / "p5-e3"]
SHARED, BLIND = "sharded_shared", "sharded_blind"


def collect() -> dict[tuple[str, str], dict]:
    rows: dict[tuple[str, str], dict] = {}
    for root in ROOTS:
        if not root.is_dir():
            continue
        for shard in sorted(p for p in root.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
            raw = json.loads((shard / "metrics.json").read_text(encoding="utf-8"))
            for arm in raw["arms"]:
                if arm["arm"] not in (SHARED, BLIND):
                    continue
                rows[(shard.name, arm["arm"])] = {
                    "elapsed": arm.get("elapsed_s") or 0.0,
                    "hits": arm["hits"],
                    "planted": arm["planted"],
                    "calls": arm["llm_calls"],
                }
    return rows


def main() -> int:
    rows = collect()
    slices = sorted({s for s, _ in rows})
    if not slices:
        print("没有数据")
        return 1

    print("| 切片 | 隔离（并发）耗时 | 共享（顺序）耗时 | 加速比 | 召回（隔离 / 共享） |")
    print("| --- | ---: | ---: | ---: | --- |")
    speedups = []
    for shard in slices:
        b, s = rows.get((shard, BLIND)), rows.get((shard, SHARED))
        if not (b and s) or not b["elapsed"]:
            continue
        speedup = s["elapsed"] / b["elapsed"]
        speedups.append(speedup)
        print(
            f"| {shard} | {b['elapsed']:.0f}s | {s['elapsed']:.0f}s | **{speedup:.2f}×** "
            f"| {b['hits']}/{b['planted']} / {s['hits']}/{s['planted']} |"
        )

    if speedups:
        avg = sum(speedups) / len(speedups)
        total_b = sum(rows[(s, BLIND)]["elapsed"] for s in slices if (s, BLIND) in rows)
        total_s = sum(rows[(s, SHARED)]["elapsed"] for s in slices if (s, SHARED) in rows)
        print(f"\n- 逐片加速比：{[f'{x:.2f}×' for x in speedups]}，均值 **{avg:.2f}×**")
        print(f"- 总耗时：并发 {total_b:.0f}s vs 顺序 {total_s:.0f}s（省 {total_s - total_b:.0f}s）")
        print(
            "\n> 两臂召回无差（隔离 3 胜 2 平），差别只在墙钟时间与调用次数。"
            "\n> 这是多智能体唯一未被否定的卖点：**同等质量下更短等待**。"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
