from pathlib import Path

from parallax.domain.models import Claim, SourceRef
from parallax.ports.reproduction import SubprocessReproductionExecutor


def claim(plan: dict) -> Claim:
    return Claim(
        claim_id="c1",
        fingerprint="f1",
        statement="repro",
        extracted_by="r1",
        source_refs=[SourceRef(evidence_id="e1", adapter="test", locator="x.py")],
        reproduction_plan=plan,
    )


def test_reproduction_executor_runs_argv_without_shell(tmp_path: Path):
    result = SubprocessReproductionExecutor(tmp_path).execute(
        claim({"command": ["python", "-c", "print('ok')"]})
    )
    assert result.status == "reproduced"
    assert "ok" in result.stdout


def test_reproduction_executor_rejects_path_escape(tmp_path: Path):
    result = SubprocessReproductionExecutor(tmp_path).execute(
        claim({"command": ["python", "-c", "pass"], "cwd": ".."})
    )
    assert result.status == "insufficient_evidence"


def test_reproduction_executor_rejects_shell_wrappers(tmp_path: Path):
    result = SubprocessReproductionExecutor(tmp_path).execute(
        claim({"command": ["sh", "-c", "echo unsafe"]})
    )
    assert result.status == "insufficient_evidence"
