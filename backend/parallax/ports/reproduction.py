"""Safe boundary for executing a Claim's minimal reproduction plan."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from parallax.domain.models import Claim

_SHELL_LAUNCHERS = {"sh", "bash", "zsh", "cmd", "cmd.exe", "powershell", "pwsh"}


class ReproductionResult(BaseModel):
    claim_id: str
    status: str
    reason: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


@runtime_checkable
class ReproductionExecutor(Protocol):
    name: str

    def execute(self, claim: Claim) -> ReproductionResult: ...


@dataclass
class SubprocessReproductionExecutor:
    """Run an explicit argv plan inside the repository boundary.

    The executor never invokes a shell, strips inherited secrets, enforces a
    timeout/output cap, and rejects paths outside the checkout. Deployments that
    need kernel-level network isolation should run this worker in a container or
    VM; the protocol keeps that stronger executor replaceable.
    """

    repo_root: Path
    timeout_s: float = 20.0
    max_output_chars: int = 20_000
    name: str = "subprocess-reproduction"

    def execute(self, claim: Claim) -> ReproductionResult:
        plan = claim.reproduction_plan or {}
        command = plan.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) and item for item in command)
        ):
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence",
                reason="reproduction_plan.command 必须是非空 argv 列表",
            )
        if Path(command[0]).name.casefold() in _SHELL_LAUNCHERS:
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence",
                reason="复现命令不得通过 shell 包装器启动",
            )
        cwd = self.repo_root
        requested_cwd = plan.get("cwd")
        if requested_cwd:
            candidate = (self.repo_root / str(requested_cwd)).resolve()
            if candidate != self.repo_root and self.repo_root not in candidate.parents:
                return ReproductionResult(
                    claim_id=claim.claim_id,
                    status="insufficient_evidence",
                    reason="复现工作目录越出仓库边界",
                )
            cwd = candidate
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                shell=False,
                capture_output=True,
                text=True,
                timeout=max(0.1, float(plan.get("timeout_s", self.timeout_s))),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence",
                reason="复现执行超时",
                stdout=str(exc.stdout or "")[-self.max_output_chars :],
                stderr=str(exc.stderr or "")[-self.max_output_chars :],
            )
        except (OSError, ValueError) as exc:
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence",
                reason=f"复现无法启动：{type(exc).__name__}: {exc}",
            )
        status = "reproduced" if result.returncode == 0 else "not_reproduced"
        return ReproductionResult(
            claim_id=claim.claim_id,
            status=status,
            reason="复现命令返回 0" if result.returncode == 0 else "复现命令返回非零状态",
            exit_code=result.returncode,
            stdout=result.stdout[-self.max_output_chars :],
            stderr=result.stderr[-self.max_output_chars :],
        )
