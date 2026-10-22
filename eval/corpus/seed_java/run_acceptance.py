"""Java defect sample acceptance: run the regression tests on the defective code, apply the reference
fix, run them again, and record both sides as evidence.

The corpus repository is never modified: every run copies it into a temporary directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SUMMARY = re.compile(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)")


def parse_reports(reports: Path) -> dict:
    per_class: dict[str, dict[str, int]] = {}
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for report in sorted(reports.glob("*.txt")):
        text = report.read_text(encoding="utf-8", errors="replace")
        match = SUMMARY.search(text)
        if not match:
            continue
        tests, failures, errors, skipped = (int(value) for value in match.groups())
        per_class[report.stem] = {
            "tests": tests,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        }
        totals["tests"] += tests
        totals["failures"] += failures
        totals["errors"] += errors
        totals["skipped"] += skipped
    return {"totals": totals, "per_class": per_class}


def run_tests(workdir: Path, maven: Path, java_home: Path, log: Path) -> dict:
    reports = workdir / "target" / "surefire-reports"
    if reports.exists():
        shutil.rmtree(reports)
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    for key in list(env):
        if key.startswith(("PARALLAX_", "SPRING_", "OPENAI_")):
            env.pop(key)
    with log.open("wb") as stream:
        result = subprocess.run(
            [str(maven), "-B", "-o", "test"],
            cwd=workdir,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=600,
        )
    parsed = parse_reports(reports)
    parsed["build_succeeded"] = result.returncode == 0
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maven", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = Path(__file__).resolve().parent
    maven = args.maven.resolve(strict=True)
    java_home = args.java_home.resolve(strict=True)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)

    defects = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))["defects"]
    package_dir = Path("src/main/java/dev/parallax/corpus/java")

    with tempfile.TemporaryDirectory(prefix="parallax-java-corpus-") as temporary:
        workdir = Path(temporary)
        for name in ("pom.xml", "src"):
            source = corpus / name
            target = workdir / name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)

        baseline = run_tests(workdir, maven, java_home, output / "baseline-maven.log")

        for reference in sorted((corpus / "reference").glob("*.java")):
            destination = workdir / package_dir / reference.name
            shutil.copyfile(reference, destination)
            # copyfile 不保留 mtime，但显式刷新一次，确保 Maven 一定重新编译修复后的源码。
            os.utime(destination, None)

        fixed = run_tests(workdir, maven, java_home, output / "fixed-maven.log")

    failing = sorted(
        name for name, counts in baseline["per_class"].items() if counts["failures"] or counts["errors"]
    )
    still_failing = sorted(
        name for name, counts in fixed["per_class"].items() if counts["failures"] or counts["errors"]
    )

    report = {
        "sample": "seed_java",
        "date": "2026-10-22",
        "planted_defects": len(defects),
        "defect_classes": sorted({defect["defect_class"] for defect in defects}),
        "baseline": baseline,
        "after_reference_fix": fixed,
        "failing_test_classes_before_fix": failing,
        "failing_test_classes_after_fix": still_failing,
        "detected_all_defects": len(failing) >= len(defects),
        "passed": (
            not baseline["build_succeeded"]
            and len(failing) >= len(defects)
            and fixed["build_succeeded"]
            and not still_failing
        ),
    }
    (output / "java-defect-sample.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"baseline failing classes={len(failing)}/{len(defects)}; "
        f"after fix failing={len(still_failing)}; passed={report['passed']}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
