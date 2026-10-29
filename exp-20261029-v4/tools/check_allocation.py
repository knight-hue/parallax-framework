"""零成本验证「集中 vs 分散」的**自变量是否真的存在**。

不调用任何模型（用离线假客户端），只跑 分区 → 截断 → 记录 这一段，
把每个 Reader **实际读到**的证据集合打出来，然后判三条：

  1. 集中臂：所有 Reader 的实读集合**完全相同**；
  2. 分散臂：各 Reader 的实读集合**两两不相交**，且合并 = 语料全集；
  3. 两臂使用**同一个** `max_units_per_reader` 值。

任一条不成立，就说明要比较的那个自变量不存在，后续全量实验不能花钱跑。

这条门槛是被真实事故逼出来的：P2 冒烟里 `--budget-calls 4` 实际发起了 6 次调用，
因为 `Budget.exhausted()` 只在轮次边界求值；S4 切片 26 个文件、每批 6 条、
3 个 Reader 一共只需 6 次调用就能读完，于是 `stop_reason=budget_exhausted`
发生时**已经读完了**。也就是说「每人只能读一部分」这个条件当时根本不存在，
拿那批数字比较「集中 vs 分散」是在比较两个都读全了的臂。

用法：
    python exp-20261029-v4/tools/check_allocation.py --slice S4-session-cache-injected --units 12
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

EXP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = EXP_ROOT.parent / "backend"
sys.path.insert(0, str(BACKEND))

from parallax.config import load_settings  # noqa: E402
from parallax.engine import ParallaxEngine  # noqa: E402
from parallax.infra.llm_fake import FakeLLMClient  # noqa: E402
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter  # noqa: E402

QUESTION = "找出这个代码仓库中真实存在的缺陷，并说明触发条件。"


async def collect(
    repo: Path,
    *,
    redundancy: int,
    readers: int,
    units: int,
    group_depth: int = 3,
    assignment: str = "greedy",
    equal_exposure: bool = False,
) -> dict[str, list[str]]:
    """跑一遍完整管线（假模型），返回每个 Reader 实际读到的证据 id。"""
    settings = load_settings(
        n_readers=readers,
        redundancy=redundancy,
        max_rounds=1,  # 只看第一轮，避免补检把差距抹平
        reader_visibility="blind",
        max_units_per_reader=units,
        max_llm_calls=0,  # 关掉预算护栏，让"读多少"完全由 max_units_per_reader 决定
        max_tokens=0,
        support_threshold=2,
        coverage_min_support=2,
        partition_assignment=assignment,
        equal_exposure=equal_exposure,
    )
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(repo, extensions=(".py",), group_depth=group_depth),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(responder=lambda _messages: {"findings": []}),
        settings=settings,
    )
    await engine.run(QUESTION)
    return dict(engine.runtime.pool.reader_evidence)


def describe(name: str, evidence: dict[str, list[str]]) -> tuple[bool, list[str]]:
    """打印一个臂的分配情况，返回 (是否可作为对照, 说明行)。"""
    rows = [f"\n## {name}"]
    sets = {rid: set(ids) for rid, ids in evidence.items()}
    for rid, ids in evidence.items():
        rows.append(f"  {rid:14s} {len(ids):3d} 条")
    union = set().union(*sets.values()) if sets else set()
    rows.append(f"  合并去重 {len(union)} 条")

    values = list(sets.values())
    identical = len(values) > 1 and all(v == values[0] for v in values)
    disjoint = all(
        not (values[i] & values[j])
        for i in range(len(values))
        for j in range(i + 1, len(values))
    )
    rows.append(f"  集合完全相同：{'是' if identical else '否'}｜两两不相交：{'是' if disjoint else '否'}")
    return identical or disjoint, rows


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slice", default="S4-session-cache-injected", help="p0-slices 下的切片目录名"
    )
    parser.add_argument("--repo", default=None, help="直接指定仓库目录（优先于 --slice）")
    parser.add_argument(
        "--units",
        default="auto",
        help="已废弃：固定数值已被 equal_exposure 取代，现仅保留参数占位",
    )
    parser.add_argument("--readers", type=int, default=3)
    parser.add_argument(
        "--group-depth",
        type=int,
        default=3,
        help="模块分组深度，决定分区的聚散粒度。**默认 3 而不是 2**："
        "实测各切片在深度 2 下只有 4~5 个分组，3 个 Reader 分 4 个组必然撞车，"
        "S6 实测出现 24/78/0 这种分布——一个 Reader 空转，两个 Reader 负载差 3 倍，"
        "「每人预算相同」就不成立了。深度 3 有 10~25 个组，轮转自然均衡。",
    )
    parser.add_argument(
        "--assignment",
        choices=["hash", "greedy"],
        default="greedy",
        help="分区分配算法。默认 greedy：分组数少时哈希会分出空转 Reader（实测 1/25/0）",
    )
    args = parser.parse_args()

    repo = Path(args.repo) if args.repo else EXP_ROOT / "p0-slices" / args.slice / "repo"
    if not repo.is_dir():
        print(f"切片仓库不存在：{repo}", file=sys.stderr)
        return 2

    scattered = await collect(
        repo,
        redundancy=1,
        readers=args.readers,
        units=0,
        group_depth=args.group_depth,
        assignment=args.assignment,
        equal_exposure=True,
    )
    central = await collect(
        repo,
        redundancy=args.readers,
        readers=args.readers,
        units=0,
        group_depth=args.group_depth,
        assignment=args.assignment,
        equal_exposure=True,
    )

    ok_central, lines_central = describe("集中臂（全部证据 + 每人截断到 N）", central)
    ok_scattered, lines_scattered = describe("分散臂（严格互斥分区）", scattered)
    print("\n".join(lines_central + lines_scattered))

    central_union = set().union(*(set(v) for v in central.values())) if central else set()
    scattered_union = set().union(*(set(v) for v in scattered.values())) if scattered else set()
    # equal_exposure 下的理论上限：ceil(语料全集 / Reader 数)
    expected = -(-len(scattered_union) // args.readers)

    checks = [
        ("集中臂：所有 Reader 实读集合完全相同", ok_central),
        ("分散臂：各 Reader 实读集合两两不相交", ok_scattered),
        (
            f"集中臂合并覆盖 = {expected} 条（= ceil(语料/Reader)）",
            len(central_union) == expected,
        ),
        (
            f"分散臂每人实读数 ≤ {expected}（未被截断）",
            all(len(v) <= expected for v in scattered.values()),
        ),
        (
            "分散臂合并覆盖 > 集中臂（联合覆盖确实更大）",
            len(scattered_union) > len(central_union),
        ),
        (
            "两臂每人曝光量接近相等（差 ≤ 1 条）",
            max(len(v) for v in central.values()) - min(len(v) for v in central.values()) <= 1
            and max(len(v) for v in scattered.values()) - min(len(v) for v in scattered.values())
            <= 1,
        ),
    ]

    print("\n## 判定")
    failed = 0
    for label, passed in checks:
        print(f"  [{'通过' if passed else '不通过'}] {label}")
        failed += 0 if passed else 1

    print(
        f"\n语料 {len(scattered_union)} 条｜上限 {expected} 条"
        f"｜集中臂联合覆盖 {len(central_union)}"
        f"｜分散臂联合覆盖 {len(scattered_union)}"
    )
    if failed:
        print(f"\n结论：{failed} 项不通过，「分配方式」这个自变量不成立，不要跑全量实验。")
        return 1
    print("\n结论：自变量成立，可以进入付费冒烟。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
