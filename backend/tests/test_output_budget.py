"""输出预算耗尽（空正文）时的拆批重发。

## 这组测试针对哪次事故

2026-10-29 的 P3 里，`deepseek-flash` 把单次输出预算烧在推理上、返回空正文
（`finish_reason='length'`，`reasoning_content` 长度约 6 万）。当时它被当成普通
`LLMError`，整批发现直接丢弃。S2 集中臂 12 次调用丢了 7 次，召回 4/10 是残值；
两臂丢弃数不等，使「分散更差」这个结论完全站不住，约 ¥110 的数据因此作废。

修复后的正确行为：

- **能拆就拆**：对半拆开重发（原样重发只会再把预算烧光一次，等于白花一遍钱）；
- **拆到单文件仍写不出来**，才记为丢批，并且必须出现在 `metrics.json` 里，
  而不是只躺在日志里等人去读。

关键点：丢批必须**可聚合**。`ReaderOutcome.error` 是字符串，没法跨臂相加，
而实验闸门需要的恰恰是「两臂丢弃数是否相等」这个能算的数字。
"""

from __future__ import annotations

from parallax.core.partitioning import Partition
from parallax.core.reader_pool import ReaderPool
from parallax.domain.errors import OutputBudgetExceeded
from parallax.ports.llm import ChatMessage
from tests.conftest import make_unit
from tests.test_reader_pool import StubPlugin

READER_ID = "reader-r0-0"


class BudgetLimitedClient:
    """一批里的文件数超过 `limit` 就模拟「推理烧穿输出预算」。

    与真实失败一致的地方：这是**成功返回了响应**但正文为空，所以钱照付，
    只是拿不到内容——这正是它危险的原因。
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.batch_sizes: list[int] = []

    async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=None):
        user = next(m.content for m in messages if m.role == "user")
        files = [
            line[len("FILE ") :] for line in user.splitlines() if line.startswith("FILE ")
        ]
        self.batch_sizes.append(len(files))
        if len(files) > self.limit:
            raise OutputBudgetExceeded(
                "模型返回了空 content（finish_reason='length'，"
                f"reasoning_content 长度=61732）。推理型模型需要更大的 max_tokens。"
            )
        return schema(findings=[{"path": path} for path in files])


def make_units(count: int):
    return [make_unit(f"f{index}.py", f"content {index}\n", "group-a") for index in range(count)]


async def run_single(pool: ReaderPool, unit_count: int):
    part = Partition(reader_id=READER_ID, round_index=0, units=tuple(make_units(unit_count)))
    outcomes = await pool.run_round(
        [part], question="q", reputation_lookup=lambda _reader: 1.0
    )
    return outcomes[0]


# ---- 拆批重发 ----


async def test_exhausted_batch_is_split_and_all_findings_survive():
    client = BudgetLimitedClient(limit=2)
    pool = ReaderPool(client=client, plugin=StubPlugin(), max_evidence_per_call=8)

    outcome = await run_single(pool, 8)

    # 8 个文件 → 拆成 4+4 → 每个 4 还是超 → 再拆成 2+2
    assert outcome.dropped_chunks == 0
    assert outcome.split_retries > 0
    assert outcome.error is None
    assert len({claim.source_refs[0].locator for claim in outcome.claims}) == 8
    assert pool.split_retries == outcome.split_retries
    assert pool.dropped_chunks == 0
    assert pool.failed_readers == []
    # 确实发生了减量：出现过不超过 limit 的批次
    assert min(client.batch_sizes) <= 2


async def test_single_file_exhaustion_is_recorded_as_dropped():
    pool = ReaderPool(
        client=BudgetLimitedClient(limit=0), plugin=StubPlugin(), max_evidence_per_call=1
    )

    outcome = await run_single(pool, 1)

    assert outcome.dropped_chunks == 1
    assert pool.dropped_chunks == 1
    assert outcome.claims == []
    assert pool.failed_readers == [READER_ID]
    assert "拆到单文件仍失败" in (outcome.error or "")


async def test_healthy_batches_are_untouched():
    pool = ReaderPool(
        client=BudgetLimitedClient(limit=6), plugin=StubPlugin(), max_evidence_per_call=6
    )

    outcome = await run_single(pool, 6)

    assert outcome.split_retries == 0
    assert outcome.dropped_chunks == 0
    assert outcome.error is None
    assert len(outcome.claims) == 6


async def test_split_retries_are_counted_in_usage_hook():
    """拆批产生的额外调用必须计入用量，否则成本统计会漏掉它们。"""
    calls: list[tuple[bool, int]] = []
    pool = ReaderPool(
        client=BudgetLimitedClient(limit=2),
        plugin=StubPlugin(),
        max_evidence_per_call=4,
        max_concurrency=1,
    )

    part = Partition(reader_id=READER_ID, round_index=0, units=tuple(make_units(4)))
    await pool.run_round(
        [part],
        question="q",
        reputation_lookup=lambda _reader: 1.0,
        usage_hook=lambda ok, retries: calls.append((ok, retries)),
    )

    # 4 → 拆 2+2：第一次失败计一次，两次成功各计一次
    assert len(calls) >= 3
    assert any(ok is False for ok, _ in calls)


# ---- 显式推理模型开关 ----


def test_llm_reasoning_override_suppresses_openai_only_fields():
    """`deepseek-flash` 会返回 reasoning_content，但名字里没有推理关键字。

    自动识别不改（改错会直接 400），改用显式开关声明；声明后不得再发
    `temperature` 与 `response_format`，否则等于对推理模型说废话甚至返回 400。
    """
    from parallax.config import Settings
    from parallax.infra.provider import build_body, resolve_profile

    settings = Settings(
        llm_api_key="test-key",
        _env_file=None,
        llm_provider="deepseek",
        llm_model="deepseek-flash",
        llm_reasoning=True,
    )
    profile = resolve_profile(settings)

    assert profile.reasoning is True
    body = build_body(
        profile,
        [ChatMessage(role="user", content="ping")],
        temperature=0.0,
        max_tokens=1000,
        json_mode=True,
        use_json_mode=True,
        reasoning_effort=None,
    )
    assert "temperature" not in body
    assert "response_format" not in body
    # DeepSeek 仍然用 max_tokens，不擅自换成未验收的字段
    assert body["max_tokens"] == 1000


def test_llm_reasoning_default_keeps_name_based_detection():
    """不声明时保持原行为——这条测试是「没有悄悄改默认」的证据。"""
    from parallax.config import Settings
    from parallax.infra.provider import resolve_profile

    settings = Settings(
        llm_api_key="test-key",
        _env_file=None,
        llm_provider="deepseek",
        llm_model="deepseek-flash",
    )
    assert resolve_profile(settings).reasoning is False
