"""缺陷注入的通用引擎：一个切片一份 spec，注入 + 生成验真测试 + 落 ground_truth。

## 为什么要把注入脚本参数化

上一版 `inject_slice_defects.py` 把 9 个缺陷写死在文件里，只能服务 S1 一个切片。
E1 要 5 个切片 × 8–12 个缺陷，写死等于写五份几乎一样的脚本，改一处要改五遍。
所以这里把「怎么注入」和「注什么」拆开：

    inject_defects.py             通用引擎（本文件）
    slice_defects/<切片名>.py      只放 INJECTIONS 与 TEST_SOURCE

## 三条硬约束（沿用上一版，改了会直接毁掉实验）

1. **每个缺陷必须有一条测试能单独打红它**——这是「它确实是缺陷」的唯一客观证据。
2. **marker 是只有被改那几行才出现的片段**，用来在测试失败后反查行号。
3. **行号在全部注入完成后再算**——前面的注入会移动后面缺陷的行号。

## 验真测试为什么写在 repo 之外

`tests_verify/` 与 `repo/` 同级：断言里写明了「应该抛什么错、应该返回什么」，
一旦放进证据池就等于把答案递给 Reader。所以它只用于验真，不参与盲读。
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slice_defects._common import Injection  # noqa: E402

P0 = Path(r"E:\开放原子大赛\抗从众的多智能体证据装配通用框架\exp-20261029-v4\p0-slices")


def load_spec(slice_name: str):
    module_name = slice_name.replace("-", "_").lower()
    module = importlib.import_module(f"slice_defects.{module_name}")
    injections: list[Injection] = module.INJECTIONS
    test_source: str = module.TEST_SOURCE
    if not injections:
        raise SystemExit(f"{slice_name} 的 INJECTIONS 为空")
    unknown = [
        i.triggers_test for i in injections if i.triggers_test.split("::")[-1] not in test_source
    ]
    if unknown:
        raise SystemExit(f"这些缺陷声明的测试在 TEST_SOURCE 里找不到：{unknown}")
    return injections, test_source


def locate(text: str, snippet: str) -> tuple[int, int]:
    index = text.find(snippet)
    if index < 0:
        raise SystemExit(f"找不到待替换片段：{snippet[:60]!r}")
    start = text.count("\n", 0, index) + 1
    end = start + snippet.rstrip("\n").count("\n")
    return start, end


def compute_reader_map(repo: Path, n_readers: int = 3, redundancy: int = 1) -> dict[str, str]:
    """用与实验完全相同的分区器算每个文件归哪个 Reader。

    必须在**注入之后**算：EvidenceUnit id 含内容哈希，内容一变、组内排序就变，
    切块归属随之改变。预先写死的归属会与真实实验不符。
    """
    try:
        from parallax.core.partitioning import BlindPartitioner
        from parallax.plugins.code_audit import RepoAdapter
    except Exception as err:  # noqa: BLE001 —— 归因信息拿不到不阻断注入
        print(f"[warn] 无法导入 parallax（{err}），reader_owner 记为空")
        return {}

    units = RepoAdapter(repo, extensions=(".py",), group_depth=2).load("审查代码中的缺陷")
    parts = BlindPartitioner(n_readers=n_readers, redundancy=redundancy, seed=0).partition(
        units, round_index=0
    )
    mapping: dict[str, str] = {}
    for part in parts:
        for unit in part.units:
            mapping.setdefault(unit.metadata.get("path", unit.locator), part.reader_id)
    return mapping


def build(slice_name: str, out_name: str | None = None, with_reader_map: bool = True) -> Path:
    injections, test_source = load_spec(slice_name)

    source = P0 / slice_name
    source_repo = source / "repo"
    if not source_repo.is_dir():
        raise SystemExit(f"{source_repo} 不存在，先跑 backend/tools/build_slices.py")

    task_dir = P0 / (out_name or f"{slice_name}-injected")
    if task_dir.exists():
        shutil.rmtree(task_dir)
    repo = task_dir / "repo"
    shutil.copytree(source_repo, repo)

    source_verify = source / "tests_verify"
    if source_verify.is_dir():
        shutil.copytree(source_verify, task_dir / "tests_verify")
    else:
        (task_dir / "tests_verify").mkdir(parents=True)

    for injection in injections:
        path = repo / injection.file
        if not path.exists():
            raise SystemExit(f"{slice_name}/{injection.defect_id}：{injection.file} 不在切片里")
        text = path.read_text(encoding="utf-8")
        for old, new in injection.edits:
            if text.count(old) != 1:
                raise SystemExit(
                    f"{injection.file} 中片段出现 {text.count(old)} 次（应为 1）：{old[:60]!r}"
                )
            text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")

    reader_map = compute_reader_map(repo) if with_reader_map else {}

    defects = []
    for injection in injections:
        text = (repo / injection.file).read_text(encoding="utf-8")
        original, new = injection.edits[-1]
        start, end = locate(text, new)
        marker_lines = new.strip().splitlines()
        defects.append(
            {
                "id": injection.defect_id,
                "file": injection.file,
                "line_start": start,
                "line_end": end,
                "defect_class": injection.defect_class,
                "title": injection.title,
                "marker": marker_lines[-1].strip() if marker_lines else "",
                "rationale": injection.rationale,
                "triggers_test": injection.triggers_test,
                "reader_owner": reader_map.get(injection.file, "unassigned"),
            }
        )

    (task_dir / "tests_verify" / "test_injected.py").write_text(test_source, encoding="utf-8")

    ground_truth = {
        "task_id": task_dir.name,
        "slice": slice_name,
        "description": f"{slice_name} 注入版：{len(defects)} 个已知缺陷，每个都有测试验真",
        "defect_count": len(defects),
        "files_touched": sorted({d["file"] for d in defects}),
        "defects": defects,
    }
    (task_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{slice_name} → {task_dir.name}")
    print(f"  缺陷 {len(defects)} 个，落在 {len(ground_truth['files_touched'])} 个文件")
    owners: dict[str, int] = {}
    for defect in defects:
        owners[defect["reader_owner"]] = owners.get(defect["reader_owner"], 0) + 1
    if reader_map:
        print(f"  按 Reader 分布：{owners}")
    return task_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slice", dest="slice_name", required=True, help="切片目录名，如 S4-session-cache"
    )
    parser.add_argument(
        "--out", dest="out_name", default=None, help="输出目录名，默认 <切片>-injected"
    )
    parser.add_argument(
        "--no-reader-map", action="store_true", help="跳过 Reader 归属计算（需要 parallax）"
    )
    args = parser.parse_args()
    build(args.slice_name, args.out_name, with_reader_map=not args.no_reader_map)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
