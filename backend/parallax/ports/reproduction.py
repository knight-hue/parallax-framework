"""Reproduction ports: trusted local execution and fail-closed Docker isolation."""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from parallax.domain.models import Claim

_SHELL_LAUNCHERS = {
    "sh",
    "bash",
    "zsh",
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
}


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


def _run_bounded(command: list[str], cwd: Path, timeout: float, cap: int) -> tuple[int, str, str]:
    """Drain both pipes continuously, retaining only bounded tails in memory."""
    env = {
        key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ
    }
    env.update(PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    tails = [b"", b""]

    def drain(stream, index):
        try:
            while data := stream.read(4096):
                tails[index] = (tails[index] + data)[-cap * 4 :]
        finally:
            stream.close()

    readers = [
        threading.Thread(target=drain, args=(stream, i), daemon=True)
        for i, stream in enumerate((process.stdout, process.stderr))
    ]
    for reader in readers:
        reader.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.kill()
        process.wait(timeout=5)
        raise
    finally:
        for reader in readers:
            reader.join(timeout=2)
    return code, *(tail.decode("utf-8", errors="replace")[-cap:] for tail in tails)


def _plan(claim: Claim, repo_root: Path, timeout_s: float) -> tuple[list[str], Path, float]:
    plan = claim.reproduction_plan or {}
    command = plan.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(arg, str) and arg and "\0" not in arg for arg in command)
    ):
        raise ValueError("reproduction_plan.command 必须是非空 argv 列表")
    if Path(command[0]).name.casefold() in _SHELL_LAUNCHERS:
        raise ValueError("复现命令不得通过 shell 包装器启动")
    root = repo_root.resolve()
    cwd = (root / str(plan.get("cwd") or ".")).resolve()
    if not cwd.is_relative_to(root) or not cwd.is_dir():
        raise ValueError("复现工作目录越出仓库边界或不存在")
    requested = float(plan.get("timeout_s", timeout_s))
    if not math.isfinite(requested) or requested <= 0:
        raise ValueError("复现超时必须是有限正数")
    return command, cwd, min(requested, timeout_s)


@dataclass
class SubprocessReproductionExecutor:
    """Only for explicitly trusted local fixtures; this is NOT a security sandbox."""

    repo_root: Path
    timeout_s: float = 20.0
    max_output_chars: int = 20_000
    name: str = "trusted-subprocess-reproduction"

    def execute(self, claim: Claim) -> ReproductionResult:
        try:
            command, cwd, timeout = _plan(claim, Path(self.repo_root), self.timeout_s)
            code, stdout, stderr = _run_bounded(command, cwd, timeout, self.max_output_chars)
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="reproduced" if code == 0 else "not_reproduced",
                reason="复现命令返回 0" if code == 0 else "复现命令返回非零状态",
                exit_code=code,
                stdout=stdout,
                stderr=stderr,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence",
                reason=f"复现未完成：{type(exc).__name__}: {exc}",
            )


@dataclass
class DockerReproductionExecutor:
    """No image pulls, no network, read-only source and bounded CPU/memory/PIDs.

    Run on a dedicated worker host. Do not expose the host Docker socket to the
    public API container. Container isolation does not defend against kernel bugs.
    """

    repo_root: Path
    image: str = "parallax-repro:local"
    timeout_s: float = 20.0
    max_output_chars: int = 20_000
    name: str = "docker-reproduction"

    def execute(self, claim: Claim) -> ReproductionResult:
        container = f"parallax-repro-{uuid.uuid4().hex}"
        try:
            command, cwd, timeout = _plan(claim, Path(self.repo_root), self.timeout_s)
            root = Path(self.repo_root).resolve()
            mount = f"type=bind,source={root},target=/workspace,readonly"
            if "," in str(root):
                raise ValueError("Docker 挂载路径不能包含逗号")
            argv = [
                "docker",
                "run",
                "--pull=never",
                "--rm",
                "--name",
                container,
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--pids-limit=64",
                "--memory=256m",
                "--cpus=1",
                "--user=65534:65534",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=32m",
                "--mount",
                mount,
                "--workdir",
                "/workspace/" + cwd.relative_to(root).as_posix(),
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--entrypoint",
                "/usr/bin/timeout",
                self.image,
                "--signal=KILL",
                str(timeout),
                *command,
            ]
            # 镜像中的 PID 1 自带期限：宿主 worker 崩溃也会自动停容器。
            code, stdout, stderr = _run_bounded(argv, root, timeout + 10, self.max_output_chars)
            unavailable = code in {124, 125, 126, 127, 137}
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence"
                if unavailable
                else ("reproduced" if code == 0 else "not_reproduced"),
                reason="沙箱不可用或命令无法启动" if unavailable else "隔离执行已完成",
                exit_code=code,
                stdout=stdout,
                stderr=stderr,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return ReproductionResult(
                claim_id=claim.claim_id,
                status="insufficient_evidence",
                reason=f"隔离执行未完成：{type(exc).__name__}: {exc}",
            )
        finally:
            with suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    ["docker", "rm", "-f", container], capture_output=True, timeout=5, check=False
                )
