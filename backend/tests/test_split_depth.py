"""拆批重发的深度上限：成本安全阀。

## 为什么单独测这个

拆批是**乘法**风险。6 个文件一批若每次都写不完，会拆成 3+3 → 2+1+2+1……，
总调用数最高可达原批次的十几倍，而且**这些调用全部照付**（失败的是正文，
不是响应；钱已经在服务端扣掉）。

没有上限的话，一个系统性的模型问题会把账单静默放大一个数量级。
2026-10-29 那次事故就是这个形态：以为在省钱的重试机制实际上在放大开销。

有上限之后：到深度上限仍写不出来 → 记成丢批 → 实验闸门拦住，不再继续烧钱。
"""

from __future__ import annotations

from parallax.core.partitioning import Partition
from parallax.core.reader_pool import ReaderPool
from parallax.domain.errors import OutputBudgetExceeded
from tests.conftest import make_unit
from tests.test_reader_pool import StubPlugin

READER_ID = "reader-r0-0"


class AlwaysExhaustedClient:
    """任何批次都写不出正文——模拟模型在这个配置下彻底不可用。"""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=None):
        user = next(m.content for m in messages if m.role == "user")
        files = [
            line[len("FILE ") :] for line in user.splitlines() if line.startswith("FILE ")
        ]
        self.batch_sizes.append(len(files))
        raise OutputBudgetExceeded(
            "模型返回了空 content（finish_reason='length'，reasoning_content 长度=61732）。"
        )


def make_units(count: int):
    return [make_unit(f"f{index}.py", f"content {index}\n", "group-a") for index in range(count)]


async def run(pool: ReaderPool, unit_count: int):
    part = Partition(reader_id=READER_ID, round_index=0, units=tuple(make_units(unit_count)))
    outcomes = await pool.run_round(
        [part], question="q", reputation_lookup=lambda _reader: 1.0
    )
    return outcomes[0]


async def test_split_depth_bounds_total_calls():
    """8 个文件、深度上限 3：调用数必须有界，不能无限二分。"""
    client = AlwaysExhaustedClient()
    pool = ReaderPool(
        client=client,
        plugin=StubPlugin(),
        max_evidence_per_call=8,
        max_split_depth=3,
    )

    outcome = await run(pool, 8)

    # 深度 0: 8；深度 1: 4+4；深度 2: 2×4；深度 3: 4×2 → 1+2+4+8 = 15 次
    assert len(client.batch_sizes) == 15
    assert outcome.split_retries == 1 + 2 + 4
    # 深度用尽后不再拆，8 个 1 文件批次全部记成丢批
    assert outcome.dropped_chunks == 8
    assert pool.dropped_chunks == 8
    assert pool.failed_readers == [READER_ID]


async def test_split_depth_zero_means_no_split():
    """深度 0 = 不拆，直接记丢批。给「宁可丢也不要放大开销」的场景用。"""
    client = AlwaysExhaustedClient()
    pool = ReaderPool(
        client=client,
        plugin=StubPlugin(),
        max_evidence_per_call=4,
        max_split_depth=0,
    )

    outcome = await run(pool, 4)

    assert len(client.batch_sizes) == 1
    assert outcome.split_retries == 0
    assert outcome.dropped_chunks == 1


async def test_split_recovers_within_depth():
    """深度够用时全部救回，丢批为 0。"""

    class LimitClient:
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
                raise OutputBudgetExceeded("空 content")
            return schema(findings=[{"path": path} for path in files])

    client = LimitClient(limit=2)
    pool = ReaderPool(
        client=client,
        plugin=StubPlugin(),
        max_evidence_per_call=8,
        max_split_depth=3,
    )

    outcome = await run(pool, 8)

    assert outcome.dropped_chunks == 0
    assert len({claim.source_refs[0].locator for claim in outcome.claims}) == 8
