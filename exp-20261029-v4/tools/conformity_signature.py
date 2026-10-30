"""零成本：从从众的「机制签名」检验，而不是只看召回。

## 为什么召回测不出从众

S1 两臂都是 9/9（满分），S4 盲读 11/12——**已经贴着天花板**。
天花板之下没有余量，共享再有害也变不成「少找一条」。

## 从众的签名是什么

不是「总数变少」，而是**多个 Reader 收敛到同一批结论**：

- **孤证减少**：本来只有 1 个 Reader 报出的缺陷，在共享臂里消失（或变得更少）
- **全员一致增加**：同一缺陷被所有 Reader 报出
- **冗余率上升 / 有效独立通道 K* 下降**：大家说的越来越像

这三项都在 `metrics.json` 里，**不花钱就能算**。

## 注意

这是「机制方向」的证据，不是因果证明。样本仍是 2 片，结论只能写倾向。
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
                defects = arm.get("defects") or []
                sole = sum(1 for d in defects if len(d["found_by"]) == 1)
                unanimous = sum(1 for d in defects if len(d["found_by"]) >= 3)
                rows[(shard.name, arm["arm"])] = {
                    "hits": arm["hits"],
                    "planted": arm["planted"],
                    "redundancy": arm["redundancy"],
                    "kstar": arm["effective_channels"],
                    "agents": arm["agent_count"],
                    "sole": sole,
                    "unanimous": unanimous,
                    "claims": arm["total_claims"],
                }
    return rows


def main() -> int:
    rows = collect()
    slices = sorted({s for s, _ in rows})
    if not slices:
        print("没有 E3b 数据")
        return 1

    print("## 逐切片对比")
    print("| 切片 | 臂 | 召回 | 孤证数 | 全员一致 | 冗余率 | K* | claim 数 |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for shard in slices:
        for arm in (BLIND, SHARED):
            row = rows.get((shard, arm))
            if row is None:
                continue
            label = "隔离" if arm == BLIND else "共享"
            print(
                f"| {shard} | **{label}** | {row['hits']}/{row['planted']} | {row['sole']} "
                f"| {row['unanimous']} | {row['redundancy']:.0%} "
                f"| {row['kstar']:.2f}/{row['agents']} | {row['claims']} |"
            )

    print("\n## 方向汇总（共享 − 隔离）")
    for metric, label, better in (
        ("sole", "孤证数", "越少越像从众"),
        ("unanimous", "全员一致数", "越多越像从众"),
        ("redundancy", "冗余率", "越高越像从众"),
        ("kstar", "有效独立通道 K*", "越低越像从众"),
    ):
        deltas = []
        for shard in slices:
            a, b = rows.get((shard, BLIND)), rows.get((shard, SHARED))
            if a and b:
                deltas.append(b[metric] - a[metric])
        if deltas:
            arrow = "一致" if all(d >= 0 for d in deltas) or all(d <= 0 for d in deltas) else "不一致"
            print(f"- **{label}**：共享−隔离 = {deltas} → 方向{arrow}（{better}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
