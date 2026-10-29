"""按切片跑 P3 的一个切片，跑完立刻打印核对行。

## 为什么要有这个脚本

P3 第一次尝试是一条 PowerShell 长命令跑完 10 次运行，结果：

1. `*>&1 | Tee-Object` 把握手失败的 native stderr 包成 `NativeCommandError`，
   管道被打断，整轮作废；
2. 中途撞上网络抖动，因为 `save_results` 只在**全部**运行结束后才落盘，
   于是已经花掉的钱换不回任何产物；
3. 长命令里的中文路径偶发被终端吃掉引号（`$repo='...'` 变成裸路径），
   命令直接不成立，白等一轮。

所以改成：**一片一次、每片独立落盘、每片结束立刻核对**。核对项就是 E1 的自变量本身：

- 集中臂：三个 Reader 实读条数相同且合并 = ⌈N/3⌉；
- 分散臂：三个 Reader 实读集合两两不相交且合并 = N；
- 两臂 `readers_failed` 都为 0。

用法：
    python exp-20261029-v4/tools/run_p3_slice.py S2
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BACKEND = EXP.parent / "backend"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
CORPUS = EXP / "p0-slices"
OUT_ROOT = EXP / "p3-e1"

SLICES = {
    "S4": "S4-session-cache-injected",
    "S1": "slice_order_b",
    "S2": "S2-discovery-injected",
    "S3": "S3-orchestration-injected",
    "S6": "S6-presentation-injected",
}
ARMS = "no_peers_all_evidence,blind_no_coverage"


def verify(out_dir: Path) -> int:
    """读完一份 metrics.json，打印分配与失败数，返回不通过的项数。"""
    raw = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    problems = 0
    for entry in raw["arms"]:
        units = entry.get("reader_units") or {}
        per = list(units.values())
        union = entry.get("reader_union", 0)
        missed = entry.get("planted", 0) - entry.get("hits", 0)
        print(
            f"  {entry['arm']:24s} 实读 {per} 合并 {union:3d}"
            f"｜召回 {entry.get('hits')}/{entry.get('planted')}（漏 {missed}）"
            f"｜调用 {entry.get('llm_calls')}"
            f"｜失败 {entry.get('llm_failures')}｜schema 重试 {entry.get('schema_retries')}"
            f"｜Reader 失败 {entry.get('readers_failed')}"
            f"｜stop={entry.get('stop_reason')}"
        )
        if not per:
            print("    ✗ 没有 reader_units，分配未生效")
            problems += 1
        if entry.get("readers_failed"):
            print("    ✗ 有 Reader 整体失败，该臂召回被低估")
            problems += 1
        if entry.get("stop_reason") != "max_rounds_reached":
            print(f"    ✗ stop_reason={entry.get('stop_reason')}，不是正常读完一轮")
            problems += 1
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slice", choices=sorted(SLICES), help="切片代号")
    args = parser.parse_args()

    task = SLICES[args.slice]
    out_dir = OUT_ROOT / args.slice
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = EXP / f"p3-e1-{args.slice}.log"

    cmd = [
        str(PYTHON),
        "-m",
        "parallax.cli",
        "experiment",
        "--corpus",
        str(CORPUS),
        "--tasks",
        task,
        "--arms",
        ARMS,
        "--readers",
        "3",
        "--equal-exposure",
        "--partition-assignment",
        "greedy",
        "--group-depth",
        "3",
        "--out",
        str(out_dir),
    ]
    env = dict(os.environ, PARALLAX_LLM_MAX_RETRIES="5")

    print(f"[{args.slice}] 任务 {task} -> {out_dir}")
    print(f"[{args.slice}] 日志 {log_path}")
    started = time.time()
    with log_path.open("w", encoding="utf-8", errors="replace") as fh:
        code = subprocess.call(cmd, cwd=str(BACKEND), stdout=fh, stderr=subprocess.STDOUT, env=env)
    elapsed = int(time.time() - started)
    print(f"[{args.slice}] 退出码 {code}｜耗时 {elapsed}s")

    if code != 0 or not (out_dir / "metrics.json").exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
        print("".join(f"    {line}\n" for line in tail).rstrip())
        return 1

    problems = verify(out_dir)
    print(f"[{args.slice}] 核对：{'全部通过' if not problems else f'{problems} 项不通过'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
