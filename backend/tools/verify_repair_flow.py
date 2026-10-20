"""Live discovery -> model patch -> explicit review -> offline Docker regression.

Run from backend; prepare prints a diff and does not execute it. Run again with
--approve <digest> only after reviewing proposal.json. Uses an existing image.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from parallax.config import Settings
from parallax.service.app import create_app


def run(args):
    out = args.out.resolve()
    source = out / "source"
    settings = Settings(
        enable_repair=True,
        enable_llm_falsifier=True,
        enable_reproduction=False,
        reproduction_image=args.image,
        n_readers=1,
        redundancy=1,
        support_threshold=1,
        coverage_min_support=1,
        max_rounds=1,
        llm_reasoning_effort="low",
        llm_timeout_s=180,
        llm_max_retries=0,
        max_schema_retries=0,
        audit_root=str(source),
        gateway_internal_token="",
        callback_url="",
    )
    state_file = out / "flow.json"
    if not args.approve and not args.revise_plan:
        source.mkdir(parents=True, exist_ok=False)
        (source / "calc.py").write_text(
            '"""Payment allocation contract: divide(a, b) returns None when b is zero.\n'
            "For nonzero b return a / b. Standard library only, Python 3.6 compatible.\n"
            'Regression runtime: /usr/bin/python3 in an offline Linux container.\n"""\n'
            "def divide(a, b):\n    return a / b\n",
            encoding="utf-8",
        )
    app = create_app(settings, runs_dir=out / "runs")
    with TestClient(app) as client:
        if args.revise_plan:
            previous = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
            response = client.post(
                f"/api/v1/audits/{previous['run_id']}/repairs",
                json={
                    "claim_id": previous["claim"]["claim_id"],
                    "plan": json.loads(args.revise_plan.read_text(encoding="utf-8")),
                },
            )
            response.raise_for_status()
            proposal = response.json()
            (out / "original-model-proposal.json").write_text(
                json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (out / "proposal.json").write_text(
                json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (out / "review.diff").write_text(proposal["patch"], encoding="utf-8")
            state_file.write_text(
                json.dumps({"run_id": proposal["run_id"], "repair_id": proposal["repair_id"]}),
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "plan": proposal["plan"],
                        "patch": proposal["patch"],
                        "approval_digest": proposal["approval_digest"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 0
        if args.approve:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            url = f"/api/v1/audits/{state['run_id']}/repairs/{state['repair_id']}"
            response = client.post(
                url + "/approve",
                json={"approval_digest": args.approve},
                headers={"X-Parallax-Operator": "local-reviewer"},
            )
            response.raise_for_status()
            payload = response.json()
            (out / "verification.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    {"status": payload["status"], "events": payload["events"]}, ensure_ascii=False
                ),
                flush=True,
            )
            return 0 if payload["status"] == "regression_passed" else 1
        response = client.post("/api/v1/audits", json={"repo_path": str(source), "max_files": 1})
        response.raise_for_status()
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            record = client.get(f"/api/v1/audits/{run_id}").json()
            if record["status"] in {"done", "failed", "canceled"}:
                break
            time.sleep(0.25)
        if record["status"] != "done":
            raise RuntimeError(f"Discovery did not complete: {record['status']}")
        claims = json.loads((out / "runs" / run_id / "claims.json").read_text(encoding="utf-8"))
        if not claims:
            raise RuntimeError("Real model found no claim; no repair success may be reported")
        claim = next((c for c in claims if c["claim_type"] == "boundary"), claims[0])
        response = client.post(
            f"/api/v1/audits/{run_id}/repairs", json={"claim_id": claim["claim_id"]}
        )
        response.raise_for_status()
        proposal = response.json()
        state_file.write_text(
            json.dumps({"run_id": run_id, "repair_id": proposal["repair_id"]}, indent=2),
            encoding="utf-8",
        )
        (out / "proposal.json").write_text(
            json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out / "review.diff").write_text(proposal["patch"], encoding="utf-8")
        print(
            json.dumps(
                {
                    "claim": claim["statement"],
                    "verification": claim["verification_status"],
                    "plan": proposal["plan"],
                    "patch": proposal["patch"],
                    "approval_digest": proposal["approval_digest"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--image", required=True, help="Locally cached image with timeout and Python"
    )
    parser.add_argument(
        "--approve", help="Exact reviewed proposal digest; never generated automatically"
    )
    parser.add_argument(
        "--revise-plan",
        type=Path,
        help="Review revision: create a fresh proposal/digest using a local plan JSON",
    )
    raise SystemExit(run(parser.parse_args()))
