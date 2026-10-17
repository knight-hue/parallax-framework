"""运行时语义的轻量 mutation audit。

每个 mutant 都在隔离的临时副本中注入一个单点错误，再运行覆盖该语义的
现有回归测试。测试若失败，说明缺陷被杀死；若通过则审计失败并返回非零。
该工具不修改工作树，也不需要模型凭据或网络。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mutant:
    name: str
    source: str
    needle: str
    replacement: str
    tests: str


ROOT = Path(__file__).resolve().parents[1]


MUTANTS = (
    Mutant(
        "fresh-reader-round",
        "parallax/core/partitioning.py",
        "reader_ids = self.reader_ids(round_index)",
        "reader_ids = self.reader_ids(0)",
        "tests/test_partitioning.py",
    ),
    Mutant(
        "reject-redundancy-over-reader-count",
        "parallax/core/partitioning.py",
        "redundancy > n_readers",
        "redundancy >= n_readers",
        "tests/test_partitioning.py",
    ),
    Mutant(
        "group-cap-floor",
        "parallax/core/partitioning.py",
        "return max(1, math.ceil(total_units / self.n_readers))",
        "return 1",
        "tests/test_partitioning.py",
    ),
    Mutant(
        "split-at-cap",
        "parallax/core/partitioning.py",
        "cap = self._group_cap(len(units))",
        "cap = 1",
        "tests/test_partitioning.py",
    ),
    Mutant(
        "rotate-chunks",
        "parallax/core/partitioning.py",
        "+ chunk_index) % self.n_readers",
        ") % self.n_readers",
        "tests/test_partitioning.py",
    ),
    Mutant(
        "distinct-reader-counts",
        "parallax/core/coverage.py",
        "counts[eid] >= support",
        "counts[eid] > support",
        "tests/test_coverage.py",
    ),
    Mutant(
        "minimum-row-support",
        "parallax/core/coverage.py",
        "min((counts[eid] for eid in eids), default=0)",
        "max((counts[eid] for eid in eids), default=0)",
        "tests/test_coverage.py",
    ),
    Mutant(
        "round-limit-inclusive",
        "parallax/core/coverage.py",
        "round_index + 1 >= max_rounds",
        "round_index + 1 > max_rounds",
        "tests/test_coverage.py",
    ),
    Mutant(
        "stop-on-no-progress",
        "parallax/core/coverage.py",
        "new_fingerprints_last_round == 0",
        "new_fingerprints_last_round < 0",
        "tests/test_coverage.py",
    ),
    Mutant(
        "unconfirmed-is-not-trigger",
        "parallax/core/coverage.py",
        "if not trigger:",
        "if trigger:",
        "tests/test_coverage.py",
    ),
    Mutant(
        "support-threshold",
        "parallax/core/independence.py",
        "value >= 2",
        "value > 2",
        "tests/test_independence.py",
    ),
    Mutant(
        "provenance-support-edge",
        "parallax/core/independence.py",
        'relation = "supports"',
        'relation = "support"',
        "tests/test_independence.py",
    ),
    Mutant(
        "provenance-conflict-edge",
        "parallax/core/independence.py",
        'relation = "supports" if left.polarity == right.polarity else "contradicts"',
        'relation = "supports" if left.polarity == right.polarity else "conflict"',
        "tests/test_independence.py",
    ),
    Mutant(
        "budget-contamination",
        "parallax/core/independence.py",
        "output_contamination or overlap_rate",
        "False and overlap_rate",
        "tests/test_independence.py",
    ),
    Mutant(
        "falsifier-missing-evidence",
        "parallax/ports/falsifier.py",
        "if not candidates:",
        "if candidates:",
        "tests/test_falsifier.py",
    ),
    Mutant(
        "falsifier-refutation-verdict",
        "parallax/ports/falsifier.py",
        'verdict="refuted"',
        'verdict="confirmed"',
        "tests/test_falsifier.py",
    ),
    Mutant(
        "falsifier-refutation-evidence",
        "parallax/ports/falsifier.py",
        "evidence_ids=sorted(refuted_ids)",
        "evidence_ids=sorted(confirmed_ids)",
        "tests/test_falsifier.py",
    ),
    Mutant(
        "payment-required-retry",
        "parallax/infra/llm_openai_compat.py",
        "response.status_code == 429",
        "response.status_code in {402, 429}",
        "tests/test_llm_client.py",
    ),
    Mutant(
        "shared-visibility-branch",
        "parallax/core/reader_pool.py",
        "if not self.is_blind:",
        "if self.is_blind:",
        "tests/test_reader_pool.py",
    ),
    Mutant(
        "failed-reader-accounting",
        "parallax/core/reader_pool.py",
        "if failed_chunks:",
        "if False:",
        "tests/test_reader_pool.py",
    ),
)


def _copy_backend(destination: Path) -> Path:
    target = destination / "backend"
    ignored = shutil.ignore_patterns(
        ".venv", ".pytest_cache", ".ruff_cache", "__pycache__", ".pytest-tmp", "runs", "eval"
    )
    shutil.copytree(ROOT, target, ignore=ignored)
    return target


def run_one(mutant: Mutant, temp_root: Path) -> bool:
    backend = _copy_backend(temp_root)
    path = backend / mutant.source
    original = path.read_text(encoding="utf-8")
    if original.count(mutant.needle) != 1:
        raise RuntimeError(
            f"{mutant.name}: mutation target occurs {original.count(mutant.needle)} times"
        )
    path.write_text(original.replace(mutant.needle, mutant.replacement, 1), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", mutant.tests, "-q"],
        cwd=backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
    )
    return result.returncode != 0


def main() -> int:
    killed = 0
    survived: list[str] = []
    with tempfile.TemporaryDirectory(prefix="parallax-mutation-") as directory:
        for index, mutant in enumerate(MUTANTS, start=1):
            try:
                dead = run_one(mutant, Path(directory) / str(index))
            except Exception as exc:  # pragma: no cover - audit runner diagnostics
                print(f"{mutant.name}: ERROR {exc}")
                survived.append(mutant.name)
                continue
            print(f"{mutant.name}: {'KILLED' if dead else 'SURVIVED'}")
            if dead:
                killed += 1
            else:
                survived.append(mutant.name)
    print(f"mutation audit: {killed}/{len(MUTANTS)} killed")
    if survived:
        print("surviving mutants: " + ", ".join(survived))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
