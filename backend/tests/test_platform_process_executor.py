import hashlib
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from parallax.config import Settings
from parallax.service.platform_executor import PlatformProcessExecutor


def task(seconds: int = 10):
    return SimpleNamespace(
        task_id="task", attempt=1, deadline=datetime.now(UTC) + timedelta(seconds=seconds)
    )


def script(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "child.py"
    path.write_text(body, encoding="utf-8")
    return path


def executor(tmp_path: Path, child: Path) -> PlatformProcessExecutor:
    return PlatformProcessExecutor(
        Settings(platform_process_terminate_grace_seconds=0.2),
        tmp_path,
        command=[sys.executable, str(child)],
    )


@pytest.mark.asyncio
async def test_process_executor_returns_verified_result(tmp_path: Path):
    child = script(
        tmp_path,
        """
import hashlib, json, sys
request = json.load(open(sys.argv[1], encoding="utf-8"))
content = '{"ok":true}'
json.dump({"content": content, "prompt_tokens": 3, "completion_tokens": 2,
           "digest": hashlib.sha256(content.encode()).hexdigest()},
          open(sys.argv[2], "w", encoding="utf-8"))
""",
    )
    value = await executor(tmp_path, child).run(
        task=task(), source_path=tmp_path, settings=Settings(), canceled=lambda: False
    )
    assert value[0] == '{"ok":true}'
    assert value[1:3] == (3, 2)
    assert value[3] == hashlib.sha256(value[0].encode()).hexdigest()


@pytest.mark.asyncio
async def test_process_executor_kills_a_child_after_deadline(tmp_path: Path):
    child = script(tmp_path, "import time\ntime.sleep(30)\n")
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await executor(tmp_path, child).run(
            task=task(seconds=1), source_path=tmp_path, settings=Settings(), canceled=lambda: False
        )
    assert time.monotonic() - started < 8


@pytest.mark.asyncio
async def test_process_executor_rejects_digest_mismatch(tmp_path: Path):
    child = script(
        tmp_path,
        """
import json, sys
json.dump({"content": "{}", "prompt_tokens": 0, "completion_tokens": 0,
           "digest": "0" * 64}, open(sys.argv[2], "w", encoding="utf-8"))
""",
    )
    with pytest.raises(RuntimeError, match="digest"):
        await executor(tmp_path, child).run(
            task=task(), source_path=tmp_path, settings=Settings(), canceled=lambda: False
        )


@pytest.mark.asyncio
async def test_process_executor_surfaces_structured_child_error(tmp_path: Path):
    child = script(
        tmp_path,
        """
import json, sys
json.dump({"error": "model unavailable"}, open(sys.argv[2], "w", encoding="utf-8"))
sys.exit(1)
""",
    )
    with pytest.raises(RuntimeError, match="model unavailable"):
        await executor(tmp_path, child).run(
            task=task(), source_path=tmp_path, settings=Settings(), canceled=lambda: False
        )
