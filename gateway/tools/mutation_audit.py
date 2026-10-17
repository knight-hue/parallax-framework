"""Run a small, deterministic mutation audit for gateway policy code.

Each mutant is applied in a temporary copy and the normal Maven test suite is
run. A surviving mutant means the regression suite failed to observe a change
in a security or lifecycle rule. The checkout itself is never modified.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mutant:
    name: str
    file: str
    needle: str
    replacement: str


MUTANTS = (
    Mutant(
        "run-status-accepts-any-value",
        "src/main/java/dev/parallax/gateway/runs/RunStatus.java",
        "|| CANCELED.equals(status);",
        "|| true;",
    ),
    Mutant(
        "proxy-whitelist-allows-everything",
        "src/main/java/dev/parallax/gateway/proxy/ProxyController.java",
        '"^/(health|ready)$"',
        '".*"',
    ),
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    survivors: list[str] = []
    for mutant in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="parallax-gateway-mutant-") as temp:
            worktree = Path(temp) / "gateway"
            shutil.copytree(
                root,
                worktree,
                ignore=shutil.ignore_patterns("target", ".git"),
            )
            path = worktree / mutant.file
            original = path.read_text(encoding="utf-8")
            if original.count(mutant.needle) != 1:
                raise RuntimeError(f"{mutant.name}: mutation target is not unique")
            path.write_text(original.replace(mutant.needle, mutant.replacement), encoding="utf-8")
            result = subprocess.run(
                ["mvn", "-B", "-DskipITs=true", "test"],
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            killed = result.returncode != 0
            print(f"{mutant.name}: {'killed' if killed else 'SURVIVED'}")
            if not killed:
                survivors.append(mutant.name)
    if survivors:
        print("surviving mutants: " + ", ".join(survivors))
        return 1
    print(f"gateway mutation audit: {len(MUTANTS)}/{len(MUTANTS)} killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
