"""零成本可行性检查：把每片压到约 30 个文件时，还能留住几条植入缺陷。

## 为什么必须先查这个

子采样省钱，但如果某片压到 30 个文件后只剩 3 条缺陷，那片召回就是 0/3 vs 2/3，
噪声比信号大，等于白跑。**这个可以在花一分钱之前算清楚。**

采样规则（两臂完全一致，可复现）：
- 以「分组」为单位整组取舍，保住语义完整性（与 BlindPartitioner 的假设一致）；
- 优先选「缺陷密度高」的组，使有限的文件里覆盖尽可能多的缺陷；
- 同密度按文件数升序、分组名升序，保证确定性。
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
TARGET_FILES = 30

SLICES = [
    ("S1", EXP / "p0-slices" / "S1-order-chain"),
    ("S2", EXP / "p0-slices" / "S2-discovery-injected"),
    ("S3", EXP / "p0-slices" / "S3-orchestration-injected"),
    ("S4", EXP / "p0-slices" / "S4-session-cache-injected"),
    ("S6", EXP / "p0-slices" / "S6-presentation-injected"),
]


def main() -> int:
    print(f"{'切片':4s} {'原文件':>6s} {'原缺陷':>6s} | {'采样文件':>8s} {'采样缺陷':>8s} {'缺陷密度':>8s} | 满足 ≥8 缺陷")
    print("-" * 78)
    ok_all = True
    for name, slice_dir in SLICES:
        gt_path = slice_dir / "ground_truth.json"
        repo = slice_dir / "repo"
        if not gt_path.exists() or not repo.is_dir():
            print(f"{name:4s} 缺文件")
            ok_all = False
            continue
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        defects = gt["defects"]
        defect_files = {d["file"] for d in defects}

        units = RepoAdapter(repo, extensions=(".py",), group_depth=3).load(QUESTION)
        by_group: dict[str, list[str]] = {}
        for unit in units:
            by_group.setdefault(unit.group, []).append(unit.locator)

        # 每组：文件数、其中的缺陷数
        group_stats = []
        for group, paths in by_group.items():
            n_defects = sum(1 for d in defects if d["file"] in set(paths))
            group_stats.append((group, len(paths), n_defects))
        group_stats.sort(key=lambda item: (-item[2] / max(1, item[1]), item[1], item[0]))

        picked_files: set[str] = set()
        for group, size, _n_defects in group_stats:
            if len(picked_files) >= TARGET_FILES:
                break
            picked_files.update(by_group[group])

        captured = [d for d in defects if d["file"] in picked_files]
        density = len(captured) / max(1, len(picked_files))
        ok = len(captured) >= 8
        ok_all = ok_all and ok
        print(
            f"{name:4s} {len(units):6d} {len(defects):6d} | "
            f"{len(picked_files):8d} {len(captured):8d} {density:8.2f} | "
            f"{'✅' if ok else '❌ 缺陷太少'}"
        )

    print()
    print("注：缺陷密度 = 采样后每文件平均缺陷数；原片密度供对照：")
    for name, slice_dir in SLICES:
        gt_path = slice_dir / "ground_truth.json"
        if not gt_path.exists():
            continue
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        units = RepoAdapter(slice_dir / "repo", extensions=(".py",), group_depth=3).load(QUESTION)
        print(f"  {name}: {len(gt['defects'])}/{len(units)} = {len(gt['defects'])/max(1,len(units)):.2f}")

    print()
    print("结论：" + ("五片都能在 ~30 文件内留住 ≥8 条缺陷，子采样方案可行。" if ok_all else "有切片留不住足够缺陷，需调整采样目标或放弃该片。"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
