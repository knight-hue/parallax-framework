"""Reader Pool 测试：输出隔离与对照组机制。"""

from __future__ import annotations

import pytest

from parallax.core.partitioning import Partition
from parallax.core.reader_pool import ReaderPool
from parallax.domain.errors import LLMError, SchemaValidationError
from parallax.domain.models import Claim, SourceRef
from parallax.infra.llm_fake import FakeLLMClient, RecordingLLMClient
from parallax.ports.llm import ChatMessage
from parallax.util import stable_id
from tests.conftest import make_unit

MARKER = "SENTINEL-CLAIM-TEXT"


class StubPlugin:
    """最小插件：把 shard 里每个文件渲染成一行，并要求返回 findings。"""

    name = "stub"

    def claim_types(self):
        return ["logic"]

    def output_schema(self):
        from pydantic import BaseModel

        class Out(BaseModel):
            findings: list[dict] = []

        return Out

    def build_messages(self, question, shard, reader_id):
        body = "\n".join(f"FILE {u.locator}" for u in shard)
        return [
            ChatMessage(role="system", content=f"审查者 {reader_id}"),
            ChatMessage(role="user", content=f"{question}\n{body}"),
        ]

    def parse(self, payload, shard, reader_id, round_index, reputation):
        claims = []
        for finding in getattr(payload, "findings", []):
            path = finding["path"]
            target = next((u for u in shard if u.locator == path), None)
            if target is None:
                continue
            claims.append(
                Claim(
                    claim_id=stable_id(reader_id, round_index, path),
                    fingerprint=f"{path}@0",
                    statement=f"{MARKER} {reader_id} {path}",
                    claim_type="logic",
                    extracted_by=reader_id,
                    round_index=round_index,
                    reputation_at_extraction=reputation,
                    source_refs=[
                        SourceRef(evidence_id=target.evidence_id, adapter="t", locator=path)
                    ],
                )
            )
        return claims


def partitions():
    """每个 Reader 恰好分到一个不同文件。

    不用 BlindPartitioner 直接切：它只保证冗余度，不保证每个 Reader 都非空；
    而空分区按设计不会调用模型，会让「提示词隔离」的断言对不上号。
    """
    units = [
        make_unit("mod_a/a.py", "# a", "mod_a"),
        make_unit("mod_b/b.py", "# b", "mod_b"),
        make_unit("mod_c/c.py", "# c", "mod_c"),
    ]
    return [Partition(f"reader-r0-{i}", 0, (unit,)) for i, unit in enumerate(units)]


def responder(messages: list[ChatMessage]):
    text = "\n".join(m.content for m in messages)
    findings = [
        {"path": line.split("FILE ", 1)[1].strip()}
        for line in text.splitlines()
        if line.startswith("FILE ")
    ]
    return {"findings": findings}


async def test_blind_mode_does_not_leak_other_readers_claims():
    """盲读的取证：任一 Reader 的提示词里都不能出现别的 Reader 的结论文本。"""
    client = RecordingLLMClient(responder=responder)
    pool = ReaderPool(client, StubPlugin(), visibility="blind")
    outcomes = await pool.run_round(partitions(), "q", lambda _a: 0.5)

    assert all(o.ok for o in outcomes)
    assert all(o.saw_prior_claims == 0 for o in outcomes)
    assert len(client.payloads) == 3, "每个非空 Reader 都应调用一次模型"

    for index, outcome in enumerate(outcomes):
        assert outcome.claims, "本测试要求每个 Reader 都产出结论"
        payload = client.payload_for(index)
        for other in outcomes:
            if other.reader_id == outcome.reader_id:
                continue
            assert f"{MARKER} {other.reader_id}" not in payload


async def test_shared_mode_exposes_prior_findings():
    """对照组：后到的 Reader 一定能看到此前全部结论。"""
    pool = ReaderPool(FakeLLMClient(responder=responder), StubPlugin(), visibility="shared")
    outcomes = await pool.run_round(partitions(), "q", lambda _a: 0.5)

    assert [o.saw_prior_claims for o in outcomes] == [0, 1, 2]
    assert all(o.claims for o in outcomes), "共享模式下仍应各自产出结论"


async def test_schema_retry_then_success():
    calls = {"n": 0}

    def flaky(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return SchemaValidationError("bad json")
        return responder(messages)

    client = FakeLLMClient(responder=flaky)
    pool = ReaderPool(client, StubPlugin(), max_schema_retries=2)
    outcomes = await pool.run_round(partitions()[:1], "q", lambda _a: 0.5)

    assert outcomes[0].ok
    assert outcomes[0].schema_retries == 1


async def test_persistent_schema_failure_is_recorded():
    client = FakeLLMClient(responder=lambda _m: SchemaValidationError("always bad"))
    pool = ReaderPool(client, StubPlugin(), max_schema_retries=1)
    outcomes = await pool.run_round(partitions()[:1], "q", lambda _a: 0.5)

    assert not outcomes[0].ok
    assert "chunk(s) failed" in (outcomes[0].error or "")
    assert outcomes[0].schema_retries == 2  # 初次 + 1 次重试


async def test_shard_is_split_into_bounded_batches():
    """分片必须再分批，否则大仓库下单次输出会被截断、整个 Reader 作废。

    这是实测踩到的坑：2712 行语料上控制组 6 个 Reader 有 5 个因输出截断而失败，
    一度把「Reader 挂了」误读成「从众导致漏检」。
    """
    units = [make_unit(f"mod/f{i}.py", f"# {i}", "mod") for i in range(10)]
    from parallax.core.partitioning import Partition

    client = RecordingLLMClient(responder=responder)
    pool = ReaderPool(client, StubPlugin(), max_evidence_per_call=3)

    outcomes = await pool.run_round([Partition("reader-x", 0, tuple(units))], "q", lambda _a: 0.5)

    # 10 个文件 / 每批 3 个 → 4 批
    assert len(client.payloads) == 4
    # 每批只包含本批的文件
    first = client.payload_for(0)
    assert "FILE mod/f0.py" in first
    assert "FILE mod/f9.py" not in first
    # 但 claims 是全部 10 个文件合并后的结果
    assert len(outcomes[0].claims) == 10


async def test_one_failed_batch_does_not_lose_others():
    """单批失败只丢该批，不能把整个 Reader 的产出清零。"""
    calls = {"n": 0}

    def flaky(messages):
        calls["n"] += 1
        if calls["n"] == 2:
            return SchemaValidationError("bad batch")
        return responder(messages)

    units = [make_unit(f"mod/f{i}.py", f"# {i}", "mod") for i in range(6)]
    from parallax.core.partitioning import Partition

    pool = ReaderPool(
        FakeLLMClient(responder=flaky), StubPlugin(), max_evidence_per_call=2, max_schema_retries=0
    )
    outcomes = await pool.run_round([Partition("reader-x", 0, tuple(units))], "q", lambda _a: 0.5)

    assert len(outcomes[0].claims) == 4, "3 批里失败 1 批，应保留其余 2 批的 4 条"
    assert "1 chunk(s) failed" in (outcomes[0].error or "")
    assert not pool.failed_readers, "还有产出的 Reader 不应被标记为失败"


async def test_invalid_batch_size_rejected():
    with pytest.raises(ValueError):
        ReaderPool(FakeLLMClient(), StubPlugin(), max_evidence_per_call=0)


async def test_failed_readers_are_tracked():
    """失败的 Reader 必须被单独记账。

    否则它造成的召回损失会被误读成「机制漏检」，让对照实验的结论失真。
    """
    client = FakeLLMClient(responder=lambda _m: SchemaValidationError("bad"))
    pool = ReaderPool(client, StubPlugin(), max_schema_retries=0)
    assert pool.failed_readers == []

    await pool.run_round(partitions(), "q", lambda _a: 0.5)
    assert len(pool.failed_readers) == 3
    assert len(set(pool.failed_readers)) == 3, "不应重复登记"


async def test_output_token_limit_is_forwarded():
    """输出上限必须显式传给模型。

    不传的话长输出会被静默截断 → JSON 不完整 → schema 失败 →
    该 Reader 的发现全部丢失，且系统性偏袒分片更小的实验组。
    """
    captured: dict = {}

    class Spy(FakeLLMClient):
        async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=None):
            captured["max_tokens"] = max_tokens
            return await super().complete_json(
                messages, schema, temperature=temperature, max_tokens=max_tokens
            )

    pool = ReaderPool(Spy(responder=responder), StubPlugin(), max_output_tokens=4096)
    await pool.run_round(partitions()[:1], "q", lambda _a: 0.5)
    assert captured["max_tokens"] == 4096


async def test_one_failure_does_not_kill_the_round():
    """单个 Reader 挂掉不该让整轮报废。"""
    calls = {"n": 0}

    def sometimes(messages):
        calls["n"] += 1
        if calls["n"] == 2:
            return LLMError("boom")
        return responder(messages)

    client = FakeLLMClient(responder=sometimes)
    pool = ReaderPool(client, StubPlugin())
    outcomes = await pool.run_round(partitions(), "q", lambda _a: 0.5)

    assert sum(1 for o in outcomes if o.ok) == 2
    assert sum(1 for o in outcomes if not o.ok) == 1


async def test_empty_partition_skips_model_call():
    """空上下文必然诱发幻觉，所以干脆不调模型。"""
    client = FakeLLMClient(responder=lambda _m: pytest.fail("不应该被调用"))
    pool = ReaderPool(client, StubPlugin())
    from parallax.core.partitioning import Partition

    outcomes = await pool.run_round([Partition("r", 0, ())], "q", lambda _a: 0.5)
    assert outcomes[0].claims == []


async def test_reputation_is_snapshotted_on_claims():
    client = FakeLLMClient(responder=responder)
    pool = ReaderPool(client, StubPlugin())
    outcomes = await pool.run_round(partitions()[:1], "q", lambda _a: 0.83)
    assert outcomes[0].claims[0].reputation_at_extraction == 0.83


def test_invalid_visibility_rejected():
    with pytest.raises(ValueError):
        ReaderPool(FakeLLMClient(), StubPlugin(), visibility="whatever")


# ---- 按累计字符数分批（真实仓库逼出来的修正）----


def fake_units(sizes: list[int]):
    """构造指定字符数的证据单元。"""
    return [make_unit(f"mod/f{i}.py", "x" * n, "mod") for i, n in enumerate(sizes)]


def chunk_sizes(units, *, max_chars: int, per_call: int = 6):
    pool = ReaderPool(
        FakeLLMClient(),
        StubPlugin(),
        max_evidence_per_call=per_call,
        max_chars_per_call=max_chars,
    )
    return [len(c) for c in pool._chunks(units)]


def test_char_limit_off_keeps_count_only_batching():
    """max_chars=0 必须退回旧行为，老结果才能复现。"""
    units = fake_units([50_000] * 7)
    assert chunk_sizes(units, max_chars=0) == [6, 1]


def test_char_limit_shrinks_batches_for_large_files():
    """真实仓库的文件平均大 8 倍，只按条数分批会让输出撞上 token 上限。"""
    units = fake_units([12_000] * 6)  # 贴近 anyio 的真实均值
    assert chunk_sizes(units, max_chars=36_000) == [3, 3]


def test_char_limit_does_not_touch_small_file_corpora():
    """合成语料（约 1.5k 字符/文件）必须完全不受影响——已发布结果依赖这一点。"""
    units = fake_units([1_500] * 12)
    assert chunk_sizes(units, max_chars=36_000) == chunk_sizes(units, max_chars=0) == [6, 6]


def test_oversized_single_file_still_gets_its_own_batch():
    """单个超大文件不会被切开——切文件会破坏 claim 的路径与行号语义。"""
    units = fake_units([200_000, 1_000, 1_000])
    assert chunk_sizes(units, max_chars=36_000) == [1, 2]


def test_every_unit_appears_exactly_once_across_batches():
    units = fake_units([9_000, 4_000, 20_000, 1_000, 15_000, 2_000])
    pool = ReaderPool(FakeLLMClient(), StubPlugin(), max_chars_per_call=25_000)
    flat = [u.evidence_id for c in pool._chunks(units) for u in c]
    assert sorted(flat) == sorted(u.evidence_id for u in units)
