"""Shared platform engine execution for inline and child-process modes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parallax.config import Settings
from parallax.engine import ParallaxEngine
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter

PLATFORM_QUESTION = "找出这个提交源码中真实存在的缺陷，并说明触发条件。"


async def run_engine(
    settings: Settings,
    source_path: Path,
    task_id: str,
    question: str = PLATFORM_QUESTION,
) -> tuple[str, int, int, str]:
    """Run the evidence engine and return content, prompt, completion and digest.

    The caller owns the surrounding lease/deadline. The child-process mode uses
    this same function so inline and isolated execution cannot drift.
    """
    client = OpenAICompatClient(settings)
    try:
        engine = ParallaxEngine.build(
            adapter=RepoAdapter(
                Path(source_path), extensions=(".py", ".java", ".js", ".ts"), max_files=300
            ),
            plugin=CodeAuditReader(),
            client=client,
            settings=settings,
        )
        report = await engine.run(question, run_id=task_id)
        payload = report.model_dump(mode="json")
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(content.encode()).hexdigest()
        usage = engine.usage_snapshot()
        return content, usage["prompt_tokens"], usage["completion_tokens"], digest
    finally:
        await client.aclose()
