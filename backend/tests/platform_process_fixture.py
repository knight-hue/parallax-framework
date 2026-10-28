"""Opt-in Java process IT fixture. Local source/model substitutions, real engine/HTTP."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import uvicorn

from parallax.config import Settings
from parallax.infra.llm_fake import FakeLLMClient
from parallax.ports.llm import UsageStats
from parallax.service import platform_engine, platform_worker
from parallax.service.app import create_app
from parallax.service.sources import ResolvedSource


class LocalModel(FakeLLMClient):
    def __init__(self, settings):
        super().__init__(
            lambda _: {
                "findings": [
                    {
                        "title": "Empty array access",
                        "defect_class": "boundary",
                        "path": "Demo.java",
                        "line_start": 2,
                        "line_end": 2,
                        "quote": "return values[0];",
                        "rationale": "An empty input throws ArrayIndexOutOfBoundsException",
                    }
                ]
            },
            usage=UsageStats(prompt_tokens=7, completion_tokens=3),
        )

    async def aclose(self):
        pass


def main():
    root, gateway, port = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    source = root / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "Demo.java").write_text(
        "class Demo { static int head(int[] values) {\nreturn values[0];\n} }\n",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        platform_url=gateway,
        gateway_internal_token="test-internal-token",
        platform_source_hosts=["github.com"],
        platform_heartbeat_seconds=0.05,
        platform_replay_seconds=0.05,
    )
    # Two modules import the client directly, so both bindings need the deterministic model.
    platform_worker.OpenAICompatClient = LocalModel
    platform_engine.OpenAICompatClient = LocalModel
    app = create_app(settings, runs_dir=root / "runs")
    worker = app.state.platform_worker
    worker.sources.resolve = lambda url, commit: ResolvedSource(source, commit, url)

    async def execute(**kwargs):
        # Slow/blocking work makes heartbeat and cancellation observable, without fees.
        if kwargs["task"].commit_sha.startswith("b"):
            await asyncio.Event().wait()
        await asyncio.sleep(0.3)
        return await worker.execute_default(**kwargs)

    worker.engine_factory = execute
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
