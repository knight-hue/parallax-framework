"""Reader Pool：一轮并发盲读。

## 输出隔离是本模块不可让步的约束

每个 Reader 只拿到自己的 `Partition`，构造消息时**只传自己的证据**，
调用完成后**也不把自己的 claim 回灌给任何其他 Reader**。
并发执行靠 `asyncio.gather` 而非多轮对话，正是为了让「互相看不到」在结构上成立，
而不是靠提示词里写一句「请不要参考他人结论」——那种约束不可验证。

Reader 之间唯一的共享物是**下一轮才生效**的声誉分（且只有分数，没有内容）。

## 为什么容忍单个 Reader 失败

一个 Reader 挂了（限流、超时、schema 三次不过）不应该让整轮报废：
剩下 N-1 个 Reader 的产出依然有效，失败原因记进 outcome 供审计。
这比「一个失败就整体重试」更省预算，也更接近真实分布式系统的做法。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from pydantic import BaseModel, Field

from parallax.core.partitioning import Partition
from parallax.domain.errors import LLMError, SchemaValidationError
from parallax.domain.models import Claim, EvidenceUnit
from parallax.ports.llm import ChatMessage, LLMClient
from parallax.ports.reader_plugin import ReaderPlugin

logger = logging.getLogger(__name__)


class ReaderOutcome(BaseModel):
    """单个 Reader 一轮的产出，成败都留痕。"""

    reader_id: str
    round_index: int
    evidence_ids: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    error: str | None = None
    schema_retries: int = 0
    saw_prior_claims: int = 0
    """本 Reader 在共享模式下看到了几条他人结论（盲读模式下恒为 0）。"""

    @property
    def ok(self) -> bool:
        return self.error is None


class ReaderPool:
    """盲读 Reader 池。

    ## visibility：本框架唯一为「对照组」保留的开关

    - `"blind"`（默认）：并发执行，Reader 之间互不可见。**这是框架的正常模式。**
    - `"shared"`：**顺序**执行，每个 Reader 会看到此前所有 Reader 的结论。
      这是传统多智能体协作的实现，用于实验的对照组。

    之所以要把对照组也做进框架而不是另写脚本：如果对照组和实验组跑在两套代码上，
    任何指标差异都无法排除「实现差异」这个替代解释。共用一条管线、只翻转一个开关，
    对照才是可信的。
    """

    def __init__(
        self,
        client: LLMClient,
        plugin: ReaderPlugin,
        max_schema_retries: int = 2,
        max_concurrency: int = 4,
        temperature: float = 0.0,
        visibility: str = "blind",
        max_output_tokens: int = 8000,
        max_evidence_per_call: int = 6,
        max_chars_per_call: int = 0,
    ) -> None:
        if visibility not in {"blind", "shared"}:
            raise ValueError("visibility 只能是 'blind' 或 'shared'")
        if max_evidence_per_call < 1:
            raise ValueError("max_evidence_per_call 至少为 1")
        self.client = client
        self.plugin = plugin
        self.max_schema_retries = max_schema_retries
        self.max_concurrency = max_concurrency
        self.temperature = temperature
        self.visibility = visibility
        self.max_output_tokens = max_output_tokens
        self.max_evidence_per_call = max_evidence_per_call
        self.max_chars_per_call = max_chars_per_call
        """单批证据的累计字符上限。0 = 只按条数分批（旧行为）。"""
        self.failed_readers: list[str] = []
        """执行失败的 Reader。必须被实验报告出来——失败者会拉低召回，
        若不计入统计就会把「Reader 挂了」误读成「漏检」。"""

    @property
    def is_blind(self) -> bool:
        return self.visibility == "blind"

    async def run_round(
        self,
        partitions: Sequence[Partition],
        question: str,
        reputation_lookup: Callable[[str], float],
        usage_hook: Callable[[bool, int], None] | None = None,
        prior_claims: Sequence[Claim] = (),
    ) -> list[ReaderOutcome]:
        """执行一轮阅读。

        Args:
            partitions: 本轮各 Reader 的分区。
            question: 统一的问题陈述（盲读模式下所有 Reader 共享的唯一输入）。
            reputation_lookup: agent_id -> 声誉分，用于在 claim 上留快照。
            usage_hook: (success, schema_retries) 回调，用于统计与预算控制。
            prior_claims: 仅共享模式有意义——喂给第一个 Reader 的既有结论。
        """
        if not self.is_blind:
            return await self._run_shared(
                partitions, question, reputation_lookup, usage_hook, prior_claims
            )

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def guarded(part: Partition) -> ReaderOutcome:
            async with semaphore:
                return await self._run_one(part, question, reputation_lookup, usage_hook)

        return list(await asyncio.gather(*(guarded(p) for p in partitions)))

    async def _run_shared(
        self,
        partitions: Sequence[Partition],
        question: str,
        reputation_lookup: Callable[[str], float],
        usage_hook: Callable[[bool, int], None] | None,
        prior_claims: Sequence[Claim],
    ) -> list[ReaderOutcome]:
        """对照组：顺序执行 + 结论互通。

        顺序不是为了省事，而是**共享语义要求它**：后一个 Reader 必须能看到
        前面 Reader 已经产出的结论，这在并发下无法保证。
        """
        shared: list[Claim] = list(prior_claims)
        outcomes: list[ReaderOutcome] = []
        for part in partitions:
            outcome = await self._run_one(
                part, question, reputation_lookup, usage_hook, shared_context=shared
            )
            outcomes.append(outcome)
            shared.extend(outcome.claims)
        return outcomes

    # ---- 内部 ----

    async def _run_one(
        self,
        part: Partition,
        question: str,
        reputation_lookup: Callable[[str], float],
        usage_hook: Callable[[bool, int], None] | None,
        shared_context: Sequence[Claim] = (),
    ) -> ReaderOutcome:
        """读一个 Reader 的全部分片。

        ⚠️ 分片会被**再切成多批**，每批一次模型调用。原因是一个真实且致命的坑：

        单次调用只能产出一段 JSON，而模型的单次输出有 token 上限。若让一个 Reader
        一次性读完 24~48 个文件并把全部发现塞进一段 JSON，输出必然被截断，
        JSON 不完整 → schema 校验失败 → **该 Reader 的发现全部丢失**。
        实测在 2712 行语料上，控制组 6 个 Reader 里有 5 个因此失败，
        一度把「Reader 挂了」误读成了「从众导致漏检」。

        分批之后每次调用的产出有界，失败被限制在单个批次内而不是整个 Reader。
        """
        outcome = ReaderOutcome(
            reader_id=part.reader_id,
            round_index=part.round_index,
            evidence_ids=part.evidence_ids,
            saw_prior_claims=len(shared_context),
        )
        if not part.units:
            # 没有证据就不调用模型——空上下文必然诱发幻觉
            return outcome

        shard = list(part.units)
        reputation = reputation_lookup(part.reader_id)
        shared_claims = list(shared_context)
        failed_chunks = 0

        for chunk in self._chunks(shard):
            claims, retries = await self._read_chunk(
                part, chunk, question, reputation, usage_hook, shared_claims
            )
            outcome.schema_retries += retries
            if claims is None:
                failed_chunks += 1
                continue
            outcome.claims.extend(claims)
            shared_claims.extend(claims)

        if failed_chunks:
            outcome.error = f"{failed_chunks} chunk(s) failed"
            if not outcome.claims:
                self._mark_failed(part.reader_id)
        return outcome

    def _chunks(self, shard: list[EvidenceUnit]) -> list[list[EvidenceUnit]]:
        """按「条数 + 累计字符数」双重上限分批，任一先到即断批。

        只按条数分批在**真实仓库**上会失效。实测：

            合成语料  平均 1,521 字符/文件  → 6 文件/批 ≈ 9,126 字符
            真实仓库  平均 11,500 字符/文件 → 6 文件/批 ≈ 69,000 字符  （8 倍）

        于是模型一次要吐出的发现太多，输出撞上 8000 token 上限被截断，
        JSON 不完整 → Reader 批量失败。这与 P0 记录的第 6 号缺陷是同一类问题，
        只是触发条件从「语料变长」变成了「文件变大」。

        字符上限默认 36,000：合成语料的 9k/批远低于它，因此**仍走 6 文件一批**，
        已发布的实验结果不受影响；而真实仓库会被收到约 3 文件/批。

        单个超大文件不会被切开——切文件会破坏 claim 的路径与行号语义，
        宁可让它独占一批。
        """
        size = self.max_evidence_per_call
        limit = self.max_chars_per_call
        if limit <= 0:
            return [shard[i : i + size] for i in range(0, len(shard), size)]

        chunks: list[list[EvidenceUnit]] = []
        current: list[EvidenceUnit] = []
        current_chars = 0
        for unit in shard:
            size_of_unit = len(unit.content)
            if current and (len(current) >= size or current_chars + size_of_unit > limit):
                chunks.append(current)
                current = []
                current_chars = 0
            current.append(unit)
            current_chars += size_of_unit
        if current:
            chunks.append(current)
        return chunks

    async def _read_chunk(
        self,
        part: Partition,
        chunk: list[EvidenceUnit],
        question: str,
        reputation: float,
        usage_hook: Callable[[bool, int], None] | None,
        shared_claims: Sequence[Claim],
    ) -> tuple[list[Claim] | None, int]:
        """读一批证据。

        Returns:
            (claim 列表或 None 表示全部重试失败, 本次消耗的 schema 重试次数)
        """
        schema = self.plugin.output_schema()
        retries = 0

        for attempt in range(self.max_schema_retries + 1):
            try:
                messages = self.plugin.build_messages(question, chunk, part.reader_id)
                if shared_claims:
                    # 只有对照组会走到这里。注入发生在框架层而非插件层，
                    # 这样同一份插件代码既能跑盲读也能跑共享，对照才有可比性。
                    messages = [
                        *messages,
                        ChatMessage(role="system", content=self._render_shared(shared_claims)),
                    ]
                payload = await self.client.complete_json(
                    messages,
                    schema,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens or None,
                )
                claims = self.plugin.parse(
                    payload, chunk, part.reader_id, part.round_index, reputation
                )
                if usage_hook:
                    usage_hook(True, retries)
                return claims, retries
            except SchemaValidationError as exc:
                retries += 1
                logger.warning(
                    "reader %s 批次校验失败（第 %d/%d 次，%d 个文件）：%s",
                    part.reader_id,
                    attempt + 1,
                    self.max_schema_retries + 1,
                    len(chunk),
                    exc,
                )
                continue
            except LLMError as exc:
                logger.warning("reader %s 批次调用失败：%s", part.reader_id, exc)
                if usage_hook:
                    usage_hook(False, retries)
                return None, retries
            except Exception as exc:  # noqa: BLE001 - 单批次失败不应拖垮整个 Reader
                logger.warning(
                    "reader %s 批次异常：%s: %s", part.reader_id, type(exc).__name__, exc
                )
                if usage_hook:
                    usage_hook(False, retries)
                return None, retries

        if usage_hook:
            usage_hook(False, retries)
        return None, retries

    def _mark_failed(self, reader_id: str) -> None:
        if reader_id not in self.failed_readers:
            self.failed_readers.append(reader_id)

    @staticmethod
    def _render_shared(claims: Sequence[Claim]) -> str:
        """把此前 Reader 的结论渲染成注入文本（仅对照组使用）。

        刻意**不**标注哪条结论来自谁、也不标注谁的声誉更高——对照组要模拟的是
        「大家互相能看到结论」这一种从众条件，而不是「能看出谁的结论更权威」。
        """
        lines = [f"- {c.statement}" for c in claims if c.polarity == 1]
        if not lines:
            return ""
        return (
            "<other-reviewers-findings>\n"
            "其他审查者在此前的工作中已经提出以下结论：\n"
            + "\n".join(lines)
            + "\n</other-reviewers-findings>"
        )


async def run_sequential(
    pool: ReaderPool,
    partitions: Sequence[Partition],
    question: str,
    reputation_lookup: Callable[[str], float],
) -> list[ReaderOutcome]:
    """顺序执行版（实验对照用）。

    顺序执行会天然串行，但**不共享输出**，所以它依然是纯净的盲读——
    可以拿来验证「并发」本身没有引入行为差异。
    """
    out: list[ReaderOutcome] = []
    for part in partitions:
        out.append(await pool._run_one(part, question, reputation_lookup, None))  # noqa: SLF001
    return out


AsyncReputationLookup = Callable[[str], Awaitable[float]]
