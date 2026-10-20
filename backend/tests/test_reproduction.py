import sys
from pathlib import Path

from parallax.domain.models import Claim, SourceRef
from parallax.ports.reproduction import SubprocessReproductionExecutor


def test_output_retention_is_bounded(tmp_path):
    result = SubprocessReproductionExecutor(tmp_path, max_output_chars=100).execute(
        claim({"command": [sys.executable, "-c", "print('a' * 1000000)"]})
    )
    assert result.exit_code == 0
    assert len(result.stdout) <= 100


def test_plan_cannot_raise_server_timeout(tmp_path):
    result = SubprocessReproductionExecutor(tmp_path, timeout_s=0.2).execute(
        claim({"command": [sys.executable, "-c", "import time; time.sleep(10)"], "timeout_s": 999})
    )
    assert result.status == "insufficient_evidence"


def test_exe_shell_launcher_is_rejected(tmp_path):
    result = SubprocessReproductionExecutor(tmp_path).execute(
        claim({"command": ["powershell.exe", "-Command", "echo unsafe"]})
    )
    assert result.status == "insufficient_evidence"


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
