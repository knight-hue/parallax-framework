"""Container isolation tests for the platform engine executor.

These tests need a Docker daemon and the ``python:3.12-slim`` image. Without them
they skip rather than fail, because the container boundary is an optional deployment
mode and a contributor machine without Docker must still be able to run the suite.
The tests prove the *boundary*: no network, read-only source, no host paths leaked,
and a hard deadline. They do not prove that a model produced a good review.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from parallax.config import Settings
from parallax.service.platform_container import PlatformContainerExecutor

IMAGE = "python:3.12-slim"

# Every child writes the same result envelope; only `verdict` differs per test.
WRITE_RESULT = """
import hashlib, json, sys
json.dump(
    {
        "content": verdict,
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "digest": hashlib.sha256(verdict.encode()).hexdigest(),
    },
    open(sys.argv[2], "w", encoding="utf-8"),
)
"""


def docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "image", "inspect", IMAGE],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return True


needs_docker = pytest.mark.skipif(not docker_ready(), reason="docker daemon or image unavailable")


def task(seconds: int = 20):
    return SimpleNamespace(
        task_id="task", attempt=1, deadline=datetime.now(UTC) + timedelta(seconds=seconds)
    )


def child(source: Path, body: str) -> Path:
    source.mkdir(parents=True, exist_ok=True)
    path = source / "child.py"
    path.write_text(body + WRITE_RESULT, encoding="utf-8")
    return path


def executor(tmp_path: Path) -> PlatformContainerExecutor:
    return PlatformContainerExecutor(
        Settings(),
        tmp_path,
        image=IMAGE,
        entrypoint=("python", "/src/child.py"),
    )


def test_arguments_enforce_the_isolation_boundary(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    argv = executor(tmp_path).arguments(name="run", work=work, source=tmp_path)
    joined = " ".join(argv)
    assert "--network none" in joined
    assert "--read-only" in joined
    assert "--cap-drop ALL" in joined
    assert "no-new-privileges:true" in joined
    assert "--user 65534:65534" in joined
    assert "--pids-limit" in joined and "--memory" in joined and "--cpus" in joined
    assert f"type=bind,source={tmp_path},target=/src,readonly" in joined
    assert f"type=bind,source={work},target=/work" in joined


@pytest.mark.asyncio
@needs_docker
async def test_container_returns_verified_result_and_hides_host_paths(tmp_path: Path):
    source = tmp_path / "source"
    child(
        source,
        """
import json, sys
verdict = json.load(open(sys.argv[1], encoding="utf-8"))["source_path"]
""",
    )
    content, prompt, completion, digest = await executor(tmp_path).run(
        task=task(), source_path=source, settings=Settings(), canceled=lambda: False
    )
    assert content == "/src"
    assert (prompt, completion) == (3, 2)
    assert digest == hashlib.sha256(content.encode()).hexdigest()


@pytest.mark.asyncio
@needs_docker
async def test_container_has_no_network(tmp_path: Path):
    source = tmp_path / "source"
    child(
        source,
        """
import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3).close()
    verdict = "network-open"
except OSError:
    verdict = "network-blocked"
""",
    )
    content, _, _, _ = await executor(tmp_path).run(
        task=task(), source_path=source, settings=Settings(), canceled=lambda: False
    )
    assert content == "network-blocked"


@pytest.mark.asyncio
@needs_docker
async def test_container_mounts_source_read_only(tmp_path: Path):
    source = tmp_path / "source"
    marker = source / "sentinel.txt"
    source.mkdir(parents=True, exist_ok=True)
    marker.write_text("original", encoding="utf-8")
    child(
        source,
        """
try:
    open("/src/sentinel.txt", "a", encoding="utf-8").write("tampered")
    verdict = "source-writable"
except OSError:
    verdict = "source-read-only"
""",
    )
    content, _, _, _ = await executor(tmp_path).run(
        task=task(), source_path=source, settings=Settings(), canceled=lambda: False
    )
    assert content == "source-read-only"
    assert marker.read_text(encoding="utf-8") == "original"


@pytest.mark.asyncio
@needs_docker
async def test_container_is_killed_after_the_deadline(tmp_path: Path):
    source = tmp_path / "source"
    child(source, "import time\ntime.sleep(120)\n")
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await executor(tmp_path).run(
            task=task(seconds=3), source_path=source, settings=Settings(), canceled=lambda: False
        )
    assert time.monotonic() - started < 30


@pytest.mark.asyncio
@needs_docker
async def test_container_digest_mismatch_is_rejected(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "child.py").write_text(
        """
import json, sys
json.dump({"content": "{}", "prompt_tokens": 0, "completion_tokens": 0,
           "digest": "0" * 64}, open(sys.argv[2], "w", encoding="utf-8"))
""",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="digest"):
        await executor(tmp_path).run(
            task=task(), source_path=source, settings=Settings(), canceled=lambda: False
        )
