"""Export whitelisted local acceptance facts without service logs or credentials.

No model calls. Does not rewrite archived model metrics/reports. Empty claim
arrays omitted by the historical writer are made explicit and documented.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def suites(paths):
    total = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    for path in paths:
        root = ET.parse(path).getroot()
        for suite in [root] if root.tag == "testsuite" else root.findall("testsuite"):
            for key in total:
                total[key] += int(suite.get(key, 0))
    return total


def main():
    backend = Path(__file__).resolve().parents[1]
    repo = backend.parent
    live = repo / "eval/real/openai-20261020-accepted"
    rows, empty = [], []
    if (live / "analysis.json").exists():
        empty = json.loads((live / "analysis.json").read_text(encoding="utf-8")).get(
            "raw_writer_omitted_empty_claim_arrays", []
        )
    for repetition in range(1, 4):
        directory = live / f"rep{repetition}"
        payload = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        for raw in payload["arms"]:
            stem = f"{raw['task_id']}__{raw['arm']}"
            path = directory / f"{stem}.claims.json"
            if not path.exists() and raw["total_claims"] == 0:
                write(path, [])
                empty.append(path.relative_to(live).as_posix())
            claims = json.loads(path.read_text(encoding="utf-8"))
            text = (directory / f"{stem}.md").read_text(encoding="utf-8")
            match = re.search(r"独立性画像：有效通道 [\d.]+ / (\d+)", text)
            assigned = int(match[1]) if match else None
            rows.append(
                {
                    "repeat": repetition,
                    "arm": raw["arm"],
                    "valid": raw["valid"],
                    "reader_failures": raw["readers_failed"],
                    "calls": raw["llm_calls"],
                    "prompt_tokens": raw["prompt_tokens"],
                    "completion_tokens": raw["completion_tokens"],
                    "claims": raw["total_claims"],
                    "not_a_defect_observations": sum(
                        c.get("stance") == "not_a_defect" for c in claims
                    ),
                    "output_effective_channels": raw["effective_channels"],
                    "output_producing_readers": raw["agent_count"],
                    "assigned_readers_from_report": assigned,
                    "output_channels_per_assigned_reader": raw["effective_channels"] / assigned
                    if assigned
                    else None,
                    "matrix_fill_rate": raw["coverage_fill_rate"],
                    "rounds": raw["rounds"],
                }
            )
    summaries = {}
    for arm in sorted({row["arm"] for row in rows}):
        arm_rows = [row for row in rows if row["arm"] == arm and row["valid"]]
        summaries[arm] = {"valid_repetitions": len(arm_rows)}
        for key in (
            "output_effective_channels",
            "output_channels_per_assigned_reader",
            "prompt_tokens",
            "completion_tokens",
            "matrix_fill_rate",
        ):
            values = [row[key] for row in arm_rows]
            summaries[arm][key] = {
                "values": values,
                "mean": statistics.fmean(values),
                "sample_std": statistics.stdev(values) if len(values) > 1 else None,
            }
    write(
        live / "analysis.json",
        {
            "postprocessing": "offline; original metrics unchanged",
            "raw_writer_omitted_empty_claim_arrays": empty,
            "rows": rows,
            "summary": summaries,
            "limitations": [
                "No ground truth; output channels are not correctness or causal independence",
                "Claim total includes not_a_defect observations",
                "Raw agent_count counts output-producing readers, not all assigned readers",
                "All accepted arms happened to stop at one round; no measured multiround gain",
                "Same assignments/calls do not imply same token cost; shared context depends on previous outputs",
                "Snapshot reports predate later support metadata and gateway fixes; see implementation.zip",
            ],
        },
    )
    out = repo / "eval/acceptance/20261020"
    write(
        out / "test-totals.json",
        {
            "python": suites([backend / "runs/final-tests.xml"]),
            "java_unit_integration": suites(
                (repo / "gateway/target/surefire-reports").glob("TEST-*.xml")
            ),
            "java_postgres_redis": suites(
                (repo / "gateway/target/failsafe-reports").glob("TEST-*.xml")
            ),
        },
    )
    write(
        out / "native-stack.json",
        json.loads(
            (backend / "runs/native-stack-final/acceptance.json").read_text(encoding="utf-8")
        ),
    )
    repair = backend / "runs/live-repair-acceptance"
    verified = json.loads((repair / "verification.json").read_text(encoding="utf-8"))
    actual = {
        p.relative_to(repair / "source").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (repair / "source").rglob("*")
        if p.is_file()
    }
    if actual != verified["source_hashes"]:
        raise RuntimeError("Original repair source differs from the audited snapshot")
    for name in ("original-model-proposal.json", "proposal.json", "verification.json"):
        payload = json.loads((repair / name).read_text(encoding="utf-8"))
        payload.pop("source", None)
        write(out / "repair" / name, payload)
    (out / "repair/review.diff").write_text(
        (repair / "review.diff").read_text(encoding="utf-8"), encoding="utf-8"
    )
    state = json.loads((repair / "flow.json").read_text(encoding="utf-8"))
    run = repair / "runs" / state["run_id"]
    for name in ("claims.json", "manifest.json", "source-hashes.json", "report.md"):
        destination = out / "repair" / name
        destination.write_text((run / name).read_text(encoding="utf-8"), encoding="utf-8")
    write(
        out / "repair/runtime.json",
        {
            "image": "ibmcom/db2:latest",
            "python": "3.6.8",
            "purpose": "cached-image isolation demonstration only; not a recommended production runtime",
            "network": "none",
            "pull": "never",
            "original_source_changed": False,
            "review_revision": "model command import path corrected and nonzero-input assertions added before approval",
        },
    )
    print(
        json.dumps(
            {"valid_model_arms": sum(row["valid"] for row in rows), "output": str(out)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
