"""Container-isolated executor for platform review tasks.

The child-process executor stops a stuck engine from holding the worker forever,
but it still shares the host kernel, filesystem and network namespace. This module
adds a stronger boundary: the engine runs in a throwaway container with

* ``--network none`` — the reviewed repository cannot exfiltrate anything and the
  engine cannot reach an unexpected endpoint;
* a read-only root filesystem plus a ``tmpfs`` ``/tmp`` — nothing survives the run;
* read-only source and request mounts, one writable mount for the result only;
* ``--cap-drop ALL``, ``no-new-privileges``, a pids limit, a memory limit and a
  CPU quota, so a fork bomb or a memory hog is bounded;
* an unprivileged numeric user, so a container escape inherits no host authority.

What this is **not**: a hardware VM. It shares the host kernel, so a kernel
vulnerability is still a way out. It is a container boundary, which is why the
docs call it container isolation rather than a security sandbox.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from parallax.config import Settings

logger = logging.getLogger(__name__)

SANDBOX_WORK = "/work"
SANDBOX_SOURCE = "/src"
DEFAULT_ENTRYPOINT = ("python", "-m", "parallax.service.platform_executor")


class PlatformContainerExecutor:
    """Run one engine task inside a locked-down container with a hard deadline."""

    def __init__(
        self,
        settings: Settings,
        root: Path,
        *,
        image: str | None = None,
        docker: str = "docker",
        entrypoint: tuple[str, ...] = DEFAULT_ENTRYPOINT,
    ):
        self.settings = settings
        self.root = Path(root)
        self.image = image or settings.platform_container_image
        self.docker = docker
        self.entrypoint = entrypoint

    def arguments(
        self,
        *,
        name: str,
        work: Path,
        source: Path,
    ) -> list[str]:
        """Build the ``docker run`` argv. Pure, so a test can assert the isolation flags."""
        settings = self.settings
        return [
            self.docker,
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            f"/tmp:rw,size={settings.platform_container_tmpfs_mb}m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            str(settings.platform_container_pids),
            "--memory",
            f"{settings.platform_container_memory_mb}m",
            "--memory-swap",
            f"{settings.platform_container_memory_mb}m",
            "--cpus",
            str(settings.platform_container_cpus),
            "--user",
            "65534:65534",
            "--mount",
            f"type=bind,source={work},target={SANDBOX_WORK}",
            "--mount",
            f"type=bind,source={source},target={SANDBOX_SOURCE},readonly",
            "--workdir",
            SANDBOX_WORK,
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONUNBUFFERED=1",
            "--env",
            "TMPDIR=/tmp",
            self.image,
            *self.entrypoint,
            f"{SANDBOX_WORK}/request.json",
            f"{SANDBOX_WORK}/result.json",
        ]

    async def run(
        self,
        *,
        task: SimpleNamespace,
        source_path: Path,
        settings: Settings,
        canceled: Callable[[], bool],
    ) -> tuple[str, int, int, str]:
        work = self.root / "container-runs" / f"{task.task_id}-{task.attempt}-{uuid.uuid4().hex}"
        work.mkdir(parents=True, exist_ok=False)
        name = f"parallax-task-{uuid.uuid4().hex}"
        request_path = work / "request.json"
        result_path = work / "result.json"
        request_path.write_text(
            json.dumps(
                {
                    "task_id": task.task_id,
                    # The engine sees the sandbox path, never the host path.
                    "source_path": SANDBOX_SOURCE,
                    "policy": {
                        "readers": settings.n_readers,
                        "redundancy": settings.redundancy,
                        "max_rounds": settings.max_rounds,
                        "support_threshold": settings.support_threshold,
                        "falsifier_enabled": settings.enable_llm_falsifier,
                        "token_budget": settings.max_tokens,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *self.arguments(name=name, work=work, source=Path(source_path)),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except BaseException:
            shutil.rmtree(work, ignore_errors=True)
            raise
        try:
            remaining = (task.deadline - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                raise TimeoutError("platform execution deadline exceeded")
            await asyncio.wait_for(process.wait(), timeout=remaining)
            data = self._read_result(result_path)
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            if process.returncode != 0:
                raise RuntimeError(f"platform container exited with code {process.returncode}")
            content = str(data["content"])
            prompt = int(data["prompt_tokens"])
            completion = int(data["completion_tokens"])
            digest = str(data["digest"])
            if hashlib.sha256(content.encode()).hexdigest() != digest:
                raise RuntimeError("platform container result digest mismatch")
            if canceled():
                raise asyncio.CancelledError
            return content, prompt, completion, digest
        except (TimeoutError, asyncio.CancelledError):
            await self._remove(name)
            raise
        finally:
            shutil.rmtree(work, ignore_errors=True)

    async def _remove(self, name: str) -> None:
        """``--rm`` cannot fire while the container still runs, so force-remove it."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker,
                "rm",
                "-f",
                name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(process.wait(), timeout=30)
        except (TimeoutError, OSError) as exc:  # pragma: no cover - defensive
            logger.warning("failed to remove container %s: %s", name, exc)

    def _read_result(self, path: Path) -> dict[str, object]:
        if not path.exists():
            raise RuntimeError("platform container produced no result")
        return json.loads(path.read_text(encoding="utf-8"))
