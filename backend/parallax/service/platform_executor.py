"""Killable child-process executor for platform review tasks.

This is process isolation, not a VM/container sandbox. The parent can terminate
the child when the Java lease/deadline expires, so a stuck model or parser cannot
hold the worker forever. The child receives only a source path, task id and
policy values; secrets stay in the inherited environment and are never written
to the request file.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from parallax.config import Settings
from parallax.service.platform_engine import run_engine

logger = logging.getLogger(__name__)


class PlatformProcessExecutor:
    """Run one engine task in a child Python process with a hard deadline."""

    def __init__(
        self,
        settings: Settings,
        root: Path,
        *,
        command: list[str] | None = None,
    ):
        self.settings = settings
        self.root = Path(root)
        self.backend_root = Path(__file__).resolve().parents[2]
        self.command = command or [sys.executable, "-m", "parallax.service.platform_executor"]

    async def run(
        self,
        *,
        task: SimpleNamespace,
        source_path: Path,
        settings: Settings,
        canceled: Callable[[], bool],
    ) -> tuple[str, int, int, str]:
        work = self.root / "process-runs" / f"{task.task_id}-{task.attempt}-{uuid.uuid4().hex}"
        work.mkdir(parents=True, exist_ok=False)
        request_path = work / "request.json"
        result_path = work / "result.json"
        request_path.write_text(
            json.dumps(
                {
                    "task_id": task.task_id,
                    "source_path": str(source_path),
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
        environment = os.environ.copy()
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = str(self.backend_root) + (
            os.pathsep + existing if existing else ""
        )
        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        process = await asyncio.create_subprocess_exec(
            *self.command,
            str(request_path),
            str(result_path),
            cwd=str(self.backend_root),
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            **kwargs,
        )
        try:
            remaining = (task.deadline - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                raise TimeoutError("platform execution deadline exceeded")
            await asyncio.wait_for(process.wait(), timeout=remaining)
            data = self._read_result(result_path)
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            if process.returncode != 0:
                raise RuntimeError(f"platform executor exited with code {process.returncode}")
            content = str(data["content"])
            prompt = int(data["prompt_tokens"])
            completion = int(data["completion_tokens"])
            digest = str(data["digest"])
            if hashlib.sha256(content.encode()).hexdigest() != digest:
                raise RuntimeError("platform executor result digest mismatch")
            if canceled():
                raise asyncio.CancelledError
            return content, prompt, completion, digest
        except (TimeoutError, asyncio.CancelledError):
            await self._terminate(process)
            raise
        finally:
            shutil.rmtree(work, ignore_errors=True)

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(
                process.wait(), timeout=self.settings.platform_process_terminate_grace_seconds
            )
        except TimeoutError:
            process.kill()
            await process.wait()

    @staticmethod
    def _read_result(path: Path) -> dict:
        if not path.exists():
            raise RuntimeError("platform executor produced no result")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("platform executor result is not valid JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("platform executor result has an invalid shape")
        return value


def main(argv: list[str] | None = None) -> int:
    """Child entrypoint: read request.json, run the engine, write result.json."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        return 2
    request_path, result_path = Path(arguments[0]), Path(arguments[1])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        policy = request["policy"]
        settings = Settings().model_copy(
            update={
                "n_readers": policy["readers"],
                "redundancy": policy["redundancy"],
                "max_rounds": policy["max_rounds"],
                "support_threshold": policy["support_threshold"],
                "max_tokens": policy["token_budget"],
                "enable_llm_falsifier": policy["falsifier_enabled"],
                "audit_root": "",
            }
        )
        content, prompt, completion, digest = asyncio.run(
            run_engine(settings, Path(request["source_path"]), request["task_id"])
        )
        result_path.write_text(
            json.dumps(
                {
                    "content": content,
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "digest": digest,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - the parent receives this as structured evidence
        try:
            result_path.write_text(
                json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Could not write platform executor error result")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
