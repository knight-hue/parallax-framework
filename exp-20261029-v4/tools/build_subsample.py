"""构建固定规模采样子语料，并逐片验证「等预算对照」仍然成立。

## 为什么要有子采样

结论不缩水 ⇒ 5 切片 × 2 臂都要跑。但原片规模差 4 倍（26 / 43 / 63 / 72 / 102 文件），
成本主要由读取文件数决定，而且**规模不同本来就不能跨片比召回**。

按「整组、缺陷密度优先」采到约 30 个文件后（实测五片一条缺陷都不丢），
读取量降到原来的一半，且五片终于同规模——这既省钱又修掉一个方法学缺陷。

## 必须写进材料的副作用

采样按缺陷密度选组，会把缺陷密度抬高（S6 从 0.10 抬到 0.32）。
所以：

- **臂间对照有效**（两臂看的是同一份语料，密度是共同常数）；
- **绝对召回率不能与历史全量运行比较**，只能解读为「在同等曝光下谁的联合覆盖更大」。

## 采样规则（确定性）

1. 以分组为单位整组取舍，保住语义完整性；
2. 按「缺陷密度降序、文件数升序、分组名升序」排序，依次加入直到文件数 ≥ 目标；
3. 同样的输入永远得到同样的采样结果，可复算。

用法：
    python build_subsample.py            # 只构建
    python build_subsample.py --verify   # 构建并逐片跑分配验证
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BACKEND = EXP.parent / "backend"
sys.path.insert(0, str(BACKEND))

from parallax.plugins.code_audit import RepoAdapter  # noqa: E402

QUESTION = "q"
TARGET_FILES = 30
OUT_ROOT = EXP / "p1-subsample"

SLICES = [
    ("S1", EXP / "p0-slices" / "S1-order-chain"),
    ("S2", EXP / "p0-slices" / "S2-discovery-injected"),
    ("S3", EXP / "p0-slices" / "S3-orchestration-injected"),
    ("S4", EXP / "p0-slices" / "S4-session-cache-injected"),
    ("S6", EXP / "p0-slices" / "S6-presentation-injected"),
]


def select_files(slice_dir: Path) -> tuple[set[str], list[dict], int, int]:
    """返回 (选中的相对路径集合, 全部缺陷, 原文件数, 原缺陷数)。"""
    gt = json.loads((slice_dir / "ground_truth.json").read_text(encoding="utf-8"))
    defects = gt["defects"]
    units = RepoAdapter(slice_dir / "repo", extensions=(".py",), group_depth=3).load(QUESTION)

    by_group: dict[str, list[str]] = {}
    for unit in units:
        by_group.setdefault(unit.group, []).append(unit.locator)

    stats = []
    for group, paths in by_group.items():
        path_set = set(paths)
        n_defects = sum(1 for d in defects if d["file"] in path_set)
        stats.append((group, len(paths), n_defects))
    stats.sort(key=lambda item: (-item[2] / max(1, item[1]), item[1], item[0]))

    picked: set[str] = set()
    for group, _size, _n in stats:
        if len(picked) >= TARGET_FILES:
            break
        picked.update(by_group[group])
    return picked, defects, len(units), len(defects)


def build(name: str, slice_dir: Path) -> dict | None:
    picked, defects, orig_files, orig_defects = select_files(slice_dir)
    if not picked:
        return None

    out_dir = OUT_ROOT / name
    repo_out = out_dir / "repo"
    if repo_out.exists():
        shutil.rmtree(repo_out)

    src_repo = slice_dir / "repo"
    for rel in sorted(picked):
        src = src_repo / rel
        dst = repo_out / rel
        if not src.is_file():
            print(f"  ⚠ 源文件缺失 {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    kept = [d for d in defects if d["file"] in picked]
    ground_truth = {
        "task_id": name,
        "description": f"{name} 子采样（约 {TARGET_FILES} 文件，缺陷密度优先整组选取）",
        "repo": "repo",
        "planted_defect_count": len(kept),
        "defects": kept,
    }
    (out_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = {
        "source": str(slice_dir.name),
        "target_files": TARGET_FILES,
        "original_files": orig_files,
        "sampled_files": len(picked),
        "original_defects": orig_defects,
        "sampled_defects": len(kept),
        "original_density": round(orig_defects / orig_files, 4),
        "sampled_density": round(len(kept) / max(1, len(picked)), 4),
        "note": "缺陷密度被抬高，绝对召回率不可与历史全量运行比较；仅用于臂间对照。",
    }
    (out_dir / "subsample.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="构建后逐片跑分配验证")
    args = parser.parse_args()

    print(f"{'切片':4s} {'原文件':>6s} {'采样文件':>8s} {'原缺陷':>6s} {'采样缺陷':>8s} {'密度':>10s}")
    print("-" * 60)
    built = []
    for name, slice_dir in SLICES:
        manifest = build(name, slice_dir)
        if manifest is None:
            print(f"{name:4s} 跳过（源缺失）")
            continue
        built.append(name)
        density = f"{manifest['original_density']:.2f}→{manifest['sampled_density']:.2f}"
        print(
            f"{name:4s} {manifest['original_files']:6d} {manifest['sampled_files']:8d} "
            f"{manifest['original_defects']:6d} {manifest['sampled_defects']:8d} {density:>10s}"
        )

    print(f"\n采样语料已写入 {OUT_ROOT}")

    if not args.verify:
        print("（加 --verify 可逐片跑分配验证）")
        return 0

    checker = EXP / "tools" / "check_allocation.py"
    failed = 0
    for name in built:
        print(f"\n===== {name} 分配验证 =====")
        result = subprocess.run(
            [
                sys.executable,
                str(checker),
                "--repo",
                str(OUT_ROOT / name / "repo"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        tail = [line for line in result.stdout.splitlines() if line.strip()]
        keep = [line for line in tail if ("reader-r0" in line or "不通过" in line or "语料" in line or "结论" in line)]
        print("\n".join(keep) if keep else result.stdout[-800:])
        if result.returncode != 0:
            failed += 1

    print(f"\n分配验证：{len(built) - failed}/{len(built)} 片通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
