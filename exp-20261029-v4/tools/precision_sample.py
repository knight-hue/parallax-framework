"""精确率抽样：把未匹配到植入缺陷的 claim 连同它引用的真实源码一起打印出来。

## 为什么需要

打分脚本只回答「植入的缺陷有没有被找到」（召回）。它**不回答**「报出来的问题
是不是真的」（精确率）。约 387 条 claim 里只有约 48 条落在植入缺陷上，
其余 339 条从未逐条判定——所以此前任何 precision 主张都无依据。

## 做法

从指定产物里取出未匹配的 claim，按固定种子随机抽样，然后把每条 claim 的
标题/证据，与它 `locator` 指向的文件前后几行源码一起打印。
人工读完据此判定 real / false / suggestion 三档。

## 用法

    python tools/precision_sample.py --dir p4-chat --n 15 --seed 20261030
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CORPORA = ("p1-subsample", "p0-slices")


def parse_locator(locator: str) -> tuple[str, int, int]:
    path, _, tail = locator.partition(":")
    if not tail:
        return path, 0, 0
    head, _, rest = tail.partition("-")
    try:
        start = int(head)
    except ValueError:
        return path, 0, 0
    try:
        end = int(rest) if rest else start
    except ValueError:
        end = start
    return path, start, end


def file_gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    if a[1] < b[0]:
        return b[0] - a[1]
    if b[1] < a[0]:
        return a[0] - b[1]
    return 0


def load_truth() -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for corpus in CORPORA:
        for gt in (EXP / corpus).glob("*/ground_truth.json"):
            data = json.loads(gt.read_text(encoding="utf-8"))
            index[data.get("task_id") or gt.parent.name] = data["defects"]
    return index


def repo_of(task_id: str) -> Path | None:
    for corpus in CORPORA:
        for gt in (EXP / corpus).glob("*/ground_truth.json"):
            data = json.loads(gt.read_text(encoding="utf-8"))
            if (data.get("task_id") or gt.parent.name) == task_id:
                return gt.parent / data.get("repo", "repo")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="产物子目录，如 p4-chat")
    parser.add_argument("--n", type=int, default=15)
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--window", type=int, default=7, help="源码上下文行数")
    args = parser.parse_args()

    truth = load_truth()
    pool: list[tuple[str, str, dict]] = []
    for claims_file in sorted((EXP / args.dir).rglob("*.claims.json")):
        stem = claims_file.name[: -len(".claims.json")]
        task_id, _, arm = stem.partition("__")
        if task_id not in truth:
            continue
        claims = json.loads(claims_file.read_text(encoding="utf-8"))
        if isinstance(claims, dict):
            claims = claims.get("claims", [])
        defects = truth[task_id]
        for claim in claims:
            if claim.get("stance") not in (None, "defect"):
                continue
            path, start, end = parse_locator(claim.get("locator", ""))
            matched = any(
                path == d["file"]
                and file_gap((start, end), (d["line_start"], d["line_end"])) <= 25
                for d in defects
            )
            if not matched:
                pool.append((task_id, arm, claim))

    print(f"{args.dir}: 未匹配的缺陷断言 {len(pool)} 条，抽取 {min(args.n, len(pool))} 条")
    rng = random.Random(args.seed)
    sample = rng.sample(pool, min(args.n, len(pool)))

    for index, (task_id, arm, claim) in enumerate(sample, 1):
        path, start, end = parse_locator(claim.get("locator", ""))
        print("\n" + "=" * 78)
        print(f"[{index}] {task_id} / {arm} / {claim.get('claim_id', '?')}")
        print(f"locator: {claim.get('locator')}")
        print(f"severity: {claim.get('severity')}  stance: {claim.get('stance')}")
        print(f"title: {claim.get('title')}")
        evidence = claim.get("evidence") or claim.get("detail") or ""
        evidence = re.sub(r"\s+", " ", str(evidence)).strip()
        print(f"evidence: {evidence[:600]}")
        repo = repo_of(task_id)
        if repo is None:
            print("(找不到仓库)")
            continue
        target = repo / path
        if not target.exists():
            print(f"(文件不存在: {target})")
            continue
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        lo = max(1, start - args.window)
        hi = min(len(lines), max(end, start) + args.window)
        print("-" * 60)
        for lineno in range(lo, hi + 1):
            mark = ">>" if start <= lineno <= max(end, start) else "  "
            print(f"{mark}{lineno:4d}| {lines[lineno - 1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
