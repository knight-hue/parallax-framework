"""零成本重分析：把「漏检」拆成「根本没分到」与「分到了没找到」。

## 为什么这件事值得做

S1/S2 因为丢批不均被判为不可用，但那只否定了**召回数值**，
没有否定「哪些文件被读过」这个事实——后者来自 `readers.json`，与模型无关。

于是可以问一个更干净的问题：

    在这条臂**实际读到的文件**里，植入缺陷被找到了几个？

这叫范围内召回（scope-adjusted recall）。它把两类完全不同的失败分开：

| 类别 | 含义 | 谁的锅 |
| --- | --- | --- |
| 结构性漏检 | 缺陷所在文件没有任何 Reader 读到 | **分配方式**（正是本项目的主张） |
| 执行性漏检 | 文件读到了，但没报出来 | 模型能力 / 丢批故障 |

如果「集中臂的 12 个缺陷里有 8 个所在文件根本没被读过」，那么原报的 4/12
就不能读成「模型漏了 8 个」——它主要是覆盖不足的必然结果。这正是「联合覆盖决定召回」
这个主张的**直接证据**，而且不需要再花一分钱。

## 局限（必须同时写出来，否则就是新的自欺）

丢批是整批丢的，具体丢的是哪几个文件没有落盘。所以「范围内漏检」里仍混着
丢批造成的损失，无法进一步拆分。本脚本因此**只做两分法**，不假装能三分。

用法：
    python exp-20261029-v4/tools/analyze_scope.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BACKEND = EXP.parent / "backend"
sys.path.insert(0, str(BACKEND))

from parallax.plugins.code_audit import RepoAdapter  # noqa: E402

QUESTION = "找出这个代码仓库中真实存在的缺陷，并说明触发条件。"

SLICE_REPOS = {
    "S1": EXP / "p0-slices" / "S1-order-chain" / "repo",
    "S2": EXP / "p0-slices" / "S2-discovery-injected" / "repo",
    "S4": EXP / "p0-slices" / "S4-session-cache-injected" / "repo",
}


def id_to_path(repo: Path) -> dict[str, str]:
    units = RepoAdapter(repo, extensions=(".py",), group_depth=3).load(QUESTION)
    return {unit.evidence_id: unit.locator for unit in units}


def analyse(shard: str, arm: dict, readers: dict[str, list[str]]) -> dict | None:
    repo = SLICE_REPOS.get(shard)
    if repo is None or not repo.is_dir():
        return None
    mapping = id_to_path(repo)

    read_ids = {eid for ids in readers.values() for eid in ids}
    read_paths = {mapping[eid] for eid in read_ids if eid in mapping}
    unmapped = len(read_ids) - len({eid for eid in read_ids if eid in mapping})

    defects = arm.get("defects") or []
    in_scope = [d for d in defects if d["file"] in read_paths]
    in_scope_hit = [d for d in in_scope if d["found_by"]]

    return {
        "arm": arm["arm"],
        "corpus_files": len(mapping),
        "read_files": len(read_paths),
        "unmapped": unmapped,
        "planted": len(defects),
        "hits": sum(1 for d in defects if d["found_by"]),
        "in_scope": len(in_scope),
        "in_scope_hits": len(in_scope_hit),
        "structural_misses": len(defects) - len(in_scope),
    }


def main() -> int:
    total_problems = 0
    for shard_dir in sorted((EXP / "p3-e1").iterdir()):
        if not shard_dir.is_dir() or not (shard_dir / "metrics.json").exists():
            continue
        shard = shard_dir.name
        raw = json.loads((shard_dir / "metrics.json").read_text(encoding="utf-8"))
        print(f"\n## {shard}")
        print(
            "| 臂 | 读文件/语料 | 总召回 | 范围内缺陷 | **范围内召回** | 结构性漏检 |"
        )
        print("| --- | ---: | ---: | ---: | ---: | ---: |")
        for arm in raw["arms"]:
            readers_path = next(
                shard_dir.glob(f"*__{arm['arm']}.readers.json"), None
            )
            if readers_path is None:
                print(f"| `{arm['arm']}` | — | — | — | 缺 readers.json | — |")
                total_problems += 1
                continue
            readers = json.loads(readers_path.read_text(encoding="utf-8"))
            row = analyse(shard, arm, readers)
            if row is None:
                continue
            if row["unmapped"]:
                print(f"| `{row['arm']}` | ⚠ {row['unmapped']} 个 id 无法映射 |", end="")
                total_problems += 1
            else:
                print(
                    f"| `{row['arm']}` "
                    f"| {row['read_files']}/{row['corpus_files']} ",
                    end="",
                )
            pct = (
                f"{row['in_scope_hits'] / row['in_scope']:.0%}"
                if row["in_scope"]
                else "n/a"
            )
            print(
                f"| {row['hits']}/{row['planted']} "
                f"| {row['in_scope']} "
                f"| **{row['in_scope_hits']}/{row['in_scope']} = {pct}** "
                f"| {row['structural_misses']} |"
            )
    print(
        "\n> 「结构性漏检」= 缺陷所在文件没有任何 Reader 读到，属**分配方式**的必然结果。\n"
        "> 「范围内召回」= 在实际读到的文件里找出了多少条，反映模型能力（仍混有丢批损失，无法再拆）。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
