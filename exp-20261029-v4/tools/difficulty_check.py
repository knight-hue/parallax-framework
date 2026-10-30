"""诊断：语料是不是太简单，以至于「读到就必然找到」。

## 两个判据

**判据一：范围内召回（读到就中？）**
对每个臂，只看「缺陷所在文件被该臂读到」的那些缺陷，算命中率。
若接近 100%，说明读到即找到——检测本身不难，差异纯粹来自覆盖。

**判据二：独立发现者分布（需要几个人才能找全？）**
在全读臂里，每条缺陷被 3 个 Reader 中的几个发现。
3/3 = 容易；0/3 = 三个独立视角读完都没看出来 = 这条不简单。
真正的「太简单」，应该是几乎清一色 3/3。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BACKEND = EXP.parent / "backend"
sys.path.insert(0, str(BACKEND))

from parallax.plugins.code_audit import RepoAdapter  # noqa: E402

QUESTION = "q"
CENTRAL = "no_peers_all_evidence"
DISPERSED = "blind_no_coverage"


def id_to_path(repo: Path) -> dict[str, str]:
    units = RepoAdapter(repo, extensions=(".py",), group_depth=3).load(QUESTION)
    return {unit.evidence_id: unit.locator for unit in units}


def scope_table(root: Path, corpus: Path, title: str) -> None:
    print(f"\n=== {title} ===")
    print("| 切片 | 臂 | 读到文件 | 范围内缺陷 | 范围内命中 | 范围内召回 |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for shard in sorted(p for p in root.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
        repo = corpus / shard.name / "repo"
        if not repo.is_dir():
            continue
        mapping = id_to_path(repo)
        raw = json.loads((shard / "metrics.json").read_text(encoding="utf-8"))
        for arm in raw["arms"]:
            if arm["arm"] not in (CENTRAL, DISPERSED):
                continue
            readers_path = next(shard.glob(f"*__{arm['arm']}.readers.json"), None)
            if readers_path is None:
                continue
            read_ids = {
                eid
                for ids in json.loads(readers_path.read_text(encoding="utf-8")).values()
                for eid in ids
            }
            read_paths = {mapping[eid] for eid in read_ids if eid in mapping}
            defects = arm.get("defects") or []
            in_scope = [d for d in defects if d["file"] in read_paths]
            hit = [d for d in in_scope if d["found_by"]]
            pct = f"{len(hit)/len(in_scope):.0%}" if in_scope else "n/a"
            print(
                f"| {shard.name} | `{arm['arm']}` | {len(read_paths)} "
                f"| {len(in_scope)} | {len(hit)} | **{pct}** |"
            )


def difficulty(root: Path) -> None:
    print("\n=== 独立发现者分布（全读臂：3 个 Reader 各读全部文件）===")
    print("| 切片 | 缺陷数 | 3/3 找到 | 2/3 | 1/3 | **0/3（三个都读完仍没看出）** |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for shard in sorted(p for p in root.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
        raw = json.loads((shard / "metrics.json").read_text(encoding="utf-8"))
        arm = next((a for a in raw["arms"] if a["arm"] == CENTRAL), None)
        if arm is None:
            continue
        buckets = {3: 0, 2: 0, 1: 0, 0: 0}
        for defect in arm.get("defects") or []:
            buckets[min(3, len(defect["found_by"]))] += 1
        total = sum(buckets.values())
        print(
            f"| {shard.name} | {total} | {buckets[3]} | {buckets[2]} | {buckets[1]} | **{buckets[0]}** |"
        )


def main() -> int:
    scope_table(EXP / "p4-chat", EXP / "p1-subsample", "判据一：范围内召回（chat，采样子语料，等预算）")
    scope_table(EXP / "p5-e3" / "S4" / "..", EXP / "p1-subsample", "")
    difficulty(EXP / "p5-e3")
    difficulty(EXP / "p4-chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
