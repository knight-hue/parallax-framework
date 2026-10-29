"""按 import 闭包从电商项目切出 6 个互不相同的切片，用于覆盖效应实验。

## 为什么要 6 个切片

单任务的配对检验只能给出「乐观下界」——同一任务内的缺陷共享同一批 Reader、
同一个仓库、同一套分片。6 个不同代码区域才能让「分散读优于集中读」这个结论站得住。

## 每个切片必须满足的两条

1. **文件数 30–45**：读完全部需要 5–8 批（每批 6 文件），而实验预算只给 3 批，
   这样才「读不完」——读得完时集中和分散必然打平（slice-b 那次就是这么废掉的）。
2. **能独立跑通验真测试**：把相关的 `tests/test_*.py` 复制到 `tests_verify/`（repo 之外，
   否则断言里写着的「应该抛什么错」等于把答案放进证据池）。

## 输出

    <out>/S2-discovery/repo/**           切片源码
    <out>/S2-discovery/tests_verify/**   验真测试 + conftest
    <out>/slices.json                    每片的文件数、行数、分组分布、可用测试

分组分布是分区均衡的前提：`app/infrastructure` 有 15 个文件、`app/application` 只有 3 个时，
按模块整体分配会让某些 Reader 拿到过大的一块，盲读退化成「有人读了大半」。
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

SRC = Path(r"E:\complex\电商agent\globex-agent-main")
OUT = Path(r"E:\开放原子大赛\抗从众的多智能体证据装配通用框架\exp-20261029-v4\p0-slices")

# 切片名 -> (SEEDS, 验真测试文件名)
SLICES: dict[str, tuple[list[str], list[str]]] = {
    "S2-discovery": (
        [
            "app/domain/catalog",
            "app/application/tools",
            "app/infrastructure/rag",
            "app/infrastructure/rerank",
            "app/infrastructure/embedding",
            "app/infrastructure/vector",
        ],
        ["test_retrieval.py", "test_recall_metrics.py", "test_embedding_client.py"],
    ),
    "S3-orchestration": (
        ["app/application/agents", "app/application/harness", "app/application/prompts"],
        [
            "test_harness_guards.py",
            "test_harness_middleware.py",
            "test_harness_drift.py",
            "test_harness_infra.py",
        ],
    ),
    "S4-session-cache": (
        [
            "app/domain/session",
            "app/domain/buyer",
            "app/application/memory",
            "app/infrastructure/cache",
            "app/infrastructure/security",
        ],
        [
            "test_memory_persistence.py",
            "test_preference_selector.py",
            "test_preference_tools.py",
            "test_phase4_cache.py",
            "test_rate_limit.py",
            "test_phase4_throttle.py",
        ],
    ),
    "S5-queue-events": (
        ["app/domain/queue", "app/infrastructure/queue"],
        ["test_phase4_queue.py", "test_event_contract.py", "test_event_replay.py"],
    ),
    "S6-presentation": (
        ["app/presentation", "app/worker.py", "app/composition.py"],
        ["test_logging_setup.py", "test_phase3.py", "test_tools_and_eventbus.py"],
    ),
}

CONFTEST = '''"""切片自检：把 repo 根加入 sys.path，保证 app.* 可导入。"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent / "repo"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
'''


def build_module_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for path in SRC.rglob("*.py"):
        if any(part in {"node_modules", ".venv", "__pycache__"} for part in path.parts):
            continue
        module = path.relative_to(SRC).as_posix()[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        index[module] = path.relative_to(SRC).as_posix()
    return index


def imports_of(rel: str) -> set[str]:
    try:
        tree = ast.parse((SRC / rel).read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            found.add(node.module)
            for alias in node.names:
                found.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app"):
                    found.add(alias.name)
    return found


def closure_for(seeds: list[str], index: dict[str, str]) -> set[str]:
    seed_files = [
        rel
        for module, rel in index.items()
        if any(
            module == s.replace("/", ".") or module.startswith(s.replace("/", ".") + ".")
            for s in seeds
        )
    ]
    closure: set[str] = set()
    queue = list(seed_files)
    while queue:
        rel = queue.pop()
        if rel in closure:
            continue
        closure.add(rel)
        for name in imports_of(rel):
            parts = name.split(".")
            while parts:
                candidate = ".".join(parts)
                if candidate in index:
                    target = index[candidate]
                    if target not in closure:
                        queue.append(target)
                    break
                parts.pop()
    # 补齐包 __init__.py
    for rel in list(closure):
        parts = Path(rel).parts
        for depth in range(1, len(parts)):
            init = Path(*parts[:depth]) / "__init__.py"
            if (SRC / init).exists():
                closure.add(init.as_posix())
    return closure


def main() -> int:
    index = build_module_index()
    OUT.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []

    for name, (seeds, tests) in SLICES.items():
        dest = OUT / name
        if dest.exists():
            shutil.rmtree(dest)
        repo = dest / "repo"
        repo.mkdir(parents=True)

        files = closure_for(seeds, index)
        for rel in sorted(files):
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC / rel, target)

        verify = dest / "tests_verify"
        verify.mkdir(parents=True)
        (verify / "conftest.py").write_text(CONFTEST, encoding="utf-8")
        copied_tests: list[str] = []
        for test in tests:
            source = SRC / "tests" / test
            if source.exists():
                shutil.copy2(source, verify / test)
                copied_tests.append(test)

        py_files = sorted(repo.rglob("*.py"))
        lines = sum(
            1
            for path in py_files
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        )
        groups: dict[str, int] = {}
        for path in py_files:
            rel = path.relative_to(repo).as_posix()
            parts = rel.split("/")
            group = "/".join(parts[:2]) if len(parts) > 2 else "root"
            groups[group] = groups.get(group, 0) + 1

        batches = -(-len(py_files) // 6)  # ceil(文件数 / 每批 6 个)
        summary.append(
            {
                "slice": name,
                "seeds": seeds,
                "files": len(py_files),
                "non_empty_lines": lines,
                "batches_to_read_all": batches,
                "groups": dict(sorted(groups.items(), key=lambda kv: -kv[1])),
                "verify_tests": copied_tests,
            }
        )
        print(
            f"{name:<20} {len(py_files):>3} 文件 / {lines:>5} 行 / 读完全部需 {batches} 批  "
            f"测试 {len(copied_tests)} 个"
        )

    (OUT / "slices.json").write_text(
        json.dumps({"source": str(SRC), "slices": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n清单已写入 {OUT / 'slices.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
