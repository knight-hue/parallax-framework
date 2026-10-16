"""连通性与结构化输出自检。

用法：
    .venv\\Scripts\\python.exe -m parallax.smoke

这个脚本只做三件事，全部是为了在烧实验预算之前排掉最蠢的失败：
    1. 能否用当前配置连上模型
    2. 能否拿到通过 schema 校验的 JSON（这是 Reader 能否工作的前提）
    3. 延迟与 token 用量（用于估算整轮实验的成本）
"""

from __future__ import annotations

import asyncio
import time

from pydantic import BaseModel, Field

from parallax.config import load_settings
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.ports.llm import ChatMessage


class Probe(BaseModel):
    ok: bool
    reason: str = ""
    seen_words: list[str] = Field(default_factory=list)


PROBE_TEXT = "这个函数在多线程下会丢更新：COUNTER += 1"


async def main() -> int:
    settings = load_settings()
    print(f"模型      : {settings.llm_model}")
    print(f"端点      : {settings.llm_base_url}")
    print(f"key 已配置: {bool(settings.llm_api_key)}（长度 {len(settings.llm_api_key)}）")
    print()

    client = OpenAICompatClient(settings)

    # ① 纯文本
    started = time.perf_counter()
    try:
        text = await client.complete(
            [ChatMessage(role="user", content="用一句话说明什么是竞态条件。")],
            max_tokens=128,
        )
        elapsed = time.perf_counter() - started
        print(f"[1/2] 纯文本调用 OK（{elapsed:.1f}s）")
        print(f"      返回：{text.strip()[:120]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[1/2] 纯文本调用失败：{type(exc).__name__}: {exc}")
        await client.aclose()
        return 1

    # ② 结构化 JSON（Reader 的工作方式）
    started = time.perf_counter()
    try:
        payload = await client.complete_json(
            [
                ChatMessage(
                    role="system",
                    content="判断给定代码片段是否存在并发缺陷，只输出 JSON。",
                ),
                ChatMessage(role="user", content=f"代码：{PROBE_TEXT}"),
            ],
            Probe,
            max_tokens=256,
        )
        elapsed = time.perf_counter() - started
        print(f"[2/2] 结构化输出 OK（{elapsed:.1f}s）")
        print(f"      {payload.model_dump()}")
    except Exception as exc:  # noqa: BLE001
        print(f"[2/2] 结构化输出失败：{type(exc).__name__}: {exc}")
        await client.aclose()
        return 1

    usage = client.usage
    print()
    print(
        f"用量：调用 {usage.calls} 次｜输入 {usage.prompt_tokens}｜"
        f"输出 {usage.completion_tokens}｜失败 {usage.failures}｜schema 重试 {usage.schema_retries}"
    )
    await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
