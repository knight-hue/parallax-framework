"""Repeatable live-model acceptance using an already present local checkout.

Run from backend: python tools/verify_real_model.py --repo <cached repo> --out <dir>.
Never clones repositories, installs packages, or prints credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import zipfile
from pathlib import Path

from parallax.config import Settings
from parallax.eval.experiment import ARMS, run_repo_arm, save_results
from parallax.eval.variance import render_variance
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.plugins.code_audit import RepoAdapter


async def run(args):
    base = Settings(
        n_readers=3,
        llm_timeout_s=180,
        llm_max_retries=1,
        llm_reasoning_effort="low",
        llm_max_output_tokens=10000,
        max_schema_retries=1,
        enable_llm_falsifier=False,
        max_llm_calls=24,
    )
    arms = [
        arm
        for arm in ARMS
        if arm.name
        in {"baseline_shared", "sharded_shared", "sharded_blind", "blind_no_coverage", "blind_full"}
    ]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    package = Path(__file__).resolve().parents[1] / "parallax"
    digest = hashlib.sha256()
    with zipfile.ZipFile(
        out / "implementation.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(package.rglob("*.py")):
            name = path.relative_to(package.parent.parent).as_posix()
            content = path.read_bytes()
            digest.update(name.encode())
            digest.update(content)
            archive.writestr(name, content)
    units = RepoAdapter(args.repo, max_files=args.max_files).load("audit")
    manifest = {
        "model": base.llm_model,
        "repeats": args.repeat,
        "readers": base.n_readers,
        "max_files": args.max_files,
        "ground_truth": False,
        "implementation_sha256": digest.hexdigest(),
        "corpus": [
            {"locator": unit.locator, "sha256": hashlib.sha256(unit.content.encode()).hexdigest()}
            for unit in units
        ],
        "comparison_limits": [
            "sharded_shared vs sharded_blind isolates output visibility at equal assignments/rounds",
            "blind_full adds retrieval; compare measured tokens/calls, not equal total cost",
            "no ground truth: precision and recall remain unknown",
            "same seed repeats measure provider variability, not independent dataset sampling",
        ],
    }
    (out / "acceptance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    repetitions = []
    for repetition in range(1, args.repeat + 1):
        results = []
        for arm in arms:
            print(f"repeat={repetition} arm={arm.name} started", flush=True)
            result = await run_repo_arm(
                args.repo, arm, base, OpenAICompatClient, max_files=args.max_files
            )
            result.config["implementation_sha256"] = digest.hexdigest()
            results.append(result)
            save_results(results, out / f"rep{repetition}")
            print(
                f"repeat={repetition} arm={arm.name} claims={result.metrics.total_claims} "
                f"failures={result.metrics.readers_failed} seconds={result.elapsed_s}",
                flush=True,
            )
        repetitions.append(results)
    (out / "variance.md").write_text(
        render_variance(repetitions, repo=args.repo.name), encoding="utf-8"
    )
    failed = any(
        result.errors or result.metrics.readers_failed
        for repetition in repetitions
        for result in repetition
    )
    print(f"acceptance={'FAIL' if failed else 'PASS'} output={out}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--max-files", type=int, default=3)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
