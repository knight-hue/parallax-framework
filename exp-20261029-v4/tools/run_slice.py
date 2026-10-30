"""通用分片运行器：一次只跑一个任务 × 两个臂，跑完立刻核对。

与 `run_p3_slice.py` 的区别：语料目录、任务名、输出目录、模型都由参数决定，
因此既能跑 p0-slices，也能跑 p1-subsample；既能跑 flash，也能跑 chat。

## 为什么坚持一片一条命令

- 一条命令串全部分片时，一次网络抖动就让整轮作废，而且 `save_results` 只在
  **全部**运行结束后才落盘，中途失败等于零产出（2026-10-29 已实际踩过）；
- 分片跑之后坏一片只丢一片，且每片跑完就能核对闸门，超标立即停。

用法：
    python run_slice.py --task S4 --out p4-chat/S4 --model deepseek-chat
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
ARMS = "no_peers_all_evidence,blind_no_coverage"


def verify(out_dir: Path) -> int:
    raw = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    problems = 0
    for entry in raw["arms"]:
        per = list((entry.get("reader_units") or {}).values())
        print(
            f"  {entry['arm']:24s} 实读 {per} 合并 {entry.get('reader_union', 0):3d}"
            f"｜召回 {entry.get('hits')}/{entry.get('planted')}"
            f"｜调用 {entry.get('llm_calls')}"
            f"｜失败 {entry.get('llm_failures')}｜拆批 {entry.get('split_retries')}"
            f"｜**丢批 {entry.get('dropped_chunks')}**"
            f"｜schema 重试 {entry.get('schema_retries')}"
            f"｜Reader 失败 {entry.get('readers_failed')}"
            f"｜stop={entry.get('stop_reason')}"
            f"｜入 {entry.get('prompt_tokens')} 出 {entry.get('completion_tokens')}"
        )
        if not per:
            print("    ✗ 没有 reader_units，分配未生效")
            problems += 1
        if entry.get("dropped_chunks"):
            print(f"    ✗ 丢批 {entry.get('dropped_chunks')} 个，召回残缺，不可比")
            problems += 1
        if entry.get("readers_failed"):
            print("    ✗ 有 Reader 整体失败")
            problems += 1
        if entry.get("stop_reason") != "max_rounds_reached":
            print(f"    ✗ stop_reason={entry.get('stop_reason')}")
            problems += 1
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="任务 id（p1-subsample 下的目录名）")
    parser.add_argument("--out", required=True, help="输出子目录（相对 exp-20261029-v4）")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument(
        "--corpus", default="p1-subsample", help="相对 exp-20261029-v4 的语料目录"
    )
    parser.add_argument("--arms", default=ARMS, help="逗号分隔的实验臂")
    parser.add_argument(
        "--full-read",
        action="store_true",
        help="不加 --equal-exposure（每臂按各自 redundancy 读满），用于 E3 五臂消融",
    )
    args = parser.parse_args()

    corpus = EXP / args.corpus
    out_dir = EXP / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = EXP / f"{args.out.replace('/', '-')}.log"

    cmd = [
        str(PYTHON), "-m", "parallax.cli", "experiment",
        "--corpus", str(corpus),
        "--tasks", args.task,
        "--arms", args.arms,
        "--readers", "3",
    ]
    if not args.full_read:
        cmd.append("--equal-exposure")
    cmd += [
        "--partition-assignment", "greedy",
        "--group-depth", "3",
        "--out", str(out_dir),
    ]
    env = dict(
        os.environ,
        PARALLAX_LLM_MAX_RETRIES="5",
        PARALLAX_LLM_MODEL=args.model,
    )

    print(f"[{args.task}] 语料 {corpus}")
    print(f"[{args.task}] 模型 {args.model}｜输出 {out_dir}")
    started = time.time()
    with log_path.open("w", encoding="utf-8", errors="replace") as fh:
        code = subprocess.call(
            cmd, cwd=str(BACKEND), stdout=fh, stderr=subprocess.STDOUT, env=env
        )
    print(f"[{args.task}] 退出码 {code}｜耗时 {int(time.time() - started)}s")

    if code != 0 or not (out_dir / "metrics.json").exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
        print("\n".join(f"    {line}" for line in tail))
        return 1

    problems = verify(out_dir)
    print(f"[{args.task}] 核对：{'全部通过' if not problems else f'{problems} 项不通过'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
