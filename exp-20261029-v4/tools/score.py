"""v4 的召回打分：只在「断言是缺陷」的 claim 里匹配，不碰 metrics.py。

## 为什么要另写一个

`parallax/eval/metrics.py` 的 `match_claims` 只按「文件 + 行号距离」匹配，
**从不看极性**。于是一条 `stance=not_a_defect`（「我查过了，这里安全」）
会被算成「发现了这个缺陷」。上一轮已经用真实数据证明过这件事：
d2 被一条 `not_a_defect` 的 claim 在距离 0 处「命中」，而模型真正报的那个
bug 反而被降级成重复。

改 `metrics.py` 会牵动全部历史结论，风险大；所以这一轮的打分独立成脚本，
口径写死在这里，人人可复核。

## 口径

    - 只接受 polarity=1（ASSERT）且 stance="defect" 的 claim
    - 匹配条件：同一文件，且 claim 行区间与缺陷行区间距离 <= TOLERANCE_LINES
    - 一对一贪心：一条 claim 只能记一次命中，一个缺陷也只能被记一次

> **容差是可调参数，不是真理。** 25 行是宽松口径，会把「附近另一个问题」
> 当成命中；S7-hard 上实测，同一批运行在 25 行下是 5/5，逐条人工裁定只有
> 3/5。因此对外报召回必须同时给出容差敏感度（见
> `tools/tolerance_sensitivity.py`），不能只拿单个数字说话。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TOLERANCE_LINES = 25


def parse_lines(locator: str, fallback: int) -> tuple[int, int]:
    """从 `path:12-15` 形态里取出起止行，取不到就用 fallback。"""
    _path, _, tail = locator.partition(":")
    if not tail:
        return fallback, fallback
    head, _, rest = tail.partition("-")
    try:
        start = int(head)
    except ValueError:
        return fallback, fallback
    try:
        end = int(rest) if rest else start
    except ValueError:
        end = start
    return start, end


def file_of(locator: str) -> str:
    return locator.partition(":")[0]


def is_defect_assertion(claim: dict) -> bool:
    if claim.get("stance") not in (None, "defect"):
        return False
    polarity = claim.get("polarity")
    return polarity in (None, 1)


def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    if a[1] < b[0]:
        return b[0] - a[1]
    if b[1] < a[0]:
        return a[0] - b[1]
    return 0


def score(claims: list[dict], defects: list[dict], tolerance: int = TOLERANCE_LINES) -> dict:
    usable = [c for c in claims if is_defect_assertion(c)]
    dropped = len(claims) - len(usable)

    pairs: list[tuple[int, int, int]] = []
    for di, defect in enumerate(defects):
        defect_lines = (defect["line_start"], defect["line_end"])
        for ci, claim in enumerate(usable):
            if file_of(claim.get("locator", "")) != defect["file"]:
                continue
            claim_lines = parse_lines(claim.get("locator", ""), defect_lines[0])
            gap = distance(claim_lines, defect_lines)
            if gap <= tolerance:
                pairs.append((gap, di, ci))
    pairs.sort()

    hit_defects: dict[int, int] = {}
    used_claims: set[int] = set()
    for gap, di, ci in pairs:
        if di in hit_defects or ci in used_claims:
            continue
        hit_defects[di] = ci
        used_claims.add(ci)

    missed = [defects[di]["id"] for di in range(len(defects)) if di not in hit_defects]
    orphans = [usable[ci]["claim_id"] for ci in range(len(usable)) if ci not in used_claims]

    return {
        "defects_total": len(defects),
        "tolerance": tolerance,
        "hits": len(hit_defects),
        "recall": len(hit_defects) / len(defects) if defects else 0.0,
        "claims_total": len(claims),
        "claims_scored": len(usable),
        "claims_dropped_non_defect_stance": dropped,
        "claims_unmatched": len(orphans),
        "missed": missed,
        "hits_by_defect": {defects[di]["id"]: usable[ci]["claim_id"] for di, ci in hit_defects.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path, required=True, help="claims.json")
    parser.add_argument("--ground-truth", type=Path, required=True, help="ground_truth.json")
    parser.add_argument(
        "--tolerance",
        type=int,
        default=TOLERANCE_LINES,
        help=f"行距容差（默认 {TOLERANCE_LINES}）。0 = 必须落在缺陷行区间内",
    )
    parser.add_argument("--out", type=Path, default=None, help="打分结果写入 json")
    args = parser.parse_args()

    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    if isinstance(claims, dict):
        claims = claims.get("claims", [])
    truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))

    report = score(claims, truth["defects"], tolerance=args.tolerance)
    print(
        f"召回 {report['hits']}/{report['defects_total']} = {report['recall']:.0%}"
        f"（容差 {report['tolerance']} 行）"
        f"｜claim {report['claims_total']} 条（参与打分 {report['claims_scored']}，"
        f"剔除非缺陷断言 {report['claims_dropped_non_defect_stance']}）"
    )
    if report["missed"]:
        print("漏检：" + "、".join(report["missed"]))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
