"""把分片跑出来的多份 `metrics.json` 合并成一份，供 `rerender_summary` 出总表。

## 为什么要分片跑再合并

P3 是 5 切片 × 2 臂 = 10 次运行、约 114 次模型调用、30 分钟以上。一次性跑完有两个
真实风险，第一次尝试两个都踩到了：

1. **一次网络抖动就全丢**。2026-10-29 首次尝试跑到 S1 第一个批次时撞上 8 次
   `httpx` 连接异常 + 1 次模型 JSON 畸形，整条命令夭折，已经花掉的钱换不回任何产物。
2. **只在结束时落盘**。`save_results` 在 10 次运行全部结束后才写 `metrics.json`，
   中途失败等于零产出。

分片后每片独立落盘，坏一片只丢一片，且每片结束就能核对 `readers_failed`、
`实读单元` 两列是否正常——这正是「跟进」而不是「闷跑」。

用法：
    python exp-20261029-v4/tools/merge_arms.py --root exp-20261029-v4/p3-e1 \
        --out exp-20261029-v4/p3-e1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

EXP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = EXP_ROOT.parent / "backend"
sys.path.insert(0, str(BACKEND))

from parallax.eval.experiment import rerender_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(EXP_ROOT / "p3-e1"), help="分片目录的父目录")
    parser.add_argument("--out", default=None, help="合并结果写入何处（默认同 --root）")
    args = parser.parse_args()

    root = Path(args.root)
    out = Path(args.out) if args.out else root
    out.mkdir(parents=True, exist_ok=True)

    shard_dirs = sorted(
        d for d in root.iterdir() if d.is_dir() and (d / "metrics.json").exists()
    )
    if not shard_dirs:
        print(f"{root} 下没有任何分片结果", file=sys.stderr)
        return 2

    arms: list[dict] = []
    for shard in shard_dirs:
        raw = json.loads((shard / "metrics.json").read_text(encoding="utf-8"))
        arms.extend(raw["arms"])
        # 产物一并拷到合并目录，避免「总表在 A 处、claim 明细在 B 处」
        for artifact in shard.glob("*__*.json"):
            if artifact.name == "metrics.json":
                continue
            shutil.copy2(artifact, out / artifact.name)
        for artifact in shard.glob("*__*.md"):
            shutil.copy2(artifact, out / artifact.name)

    combined = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "arms": arms,
        "shards": [d.name for d in shard_dirs],
    }
    (out / "metrics.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rerender_summary(out)

    print(f"合并 {len(shard_dirs)} 个分片、{len(arms)} 条臂结果 -> {out}")
    for shard in shard_dirs:
        print(f"  - {shard.name}")

    # 合并后立刻做一致性自检：任何一条臂缺曝光记录就说明那一片的分配没生效
    bad = [
        f"{a.get('task_id')}/{a.get('arm')}"
        for a in arms
        if not a.get("reader_units")
    ]
    if bad:
        print(f"\n⚠️ 以下臂没有 reader_units（分配未生效或产物来自旧版本）：{bad}")
        return 1
    print("\n所有臂都记录了 reader_units / reader_union，分配可核验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
