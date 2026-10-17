"""引擎：把适配器 / 插件 / 模型客户端组装成一次可运行、可复现的实验。"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from parallax.config import Settings, load_settings
from parallax.core.aggregator import AggregationRules, Aggregator
from parallax.core.coverage import CoverageMonitor
from parallax.core.independence import build_independence_profile, build_provenance_graph
from parallax.core.ledger import ClaimLedger, LedgerGroup
from parallax.core.partitioning import BlindPartitioner
from parallax.core.reader_pool import ReaderPool
from parallax.core.reputation import InMemoryReputationStore, ReputationPolicy
from parallax.domain.enums import ClaimStatus
from parallax.domain.models import Claim, Report, RunManifest
from parallax.graph.build import build_graph
from parallax.graph.state import ParallaxRuntime
from parallax.ports.arbitrator import NullArbitrator
from parallax.ports.claim_validator import ClaimValidator
from parallax.ports.evidence_adapter import EvidenceAdapter
from parallax.ports.falsifier import Falsifier
from parallax.ports.llm import LLMClient
from parallax.ports.reader_plugin import ReaderPlugin
from parallax.util import stable_id

logger = logging.getLogger(__name__)


class ParallaxEngine:
    """一次运行的全部装配。"""

    def __init__(
        self,
        runtime: ParallaxRuntime,
        adapter: EvidenceAdapter,
        plugin: ReaderPlugin,
    ) -> None:
        self.runtime = runtime
        self.adapter = adapter
        self.plugin = plugin
        self._graph = build_graph(runtime)

    # ---- 装配 ----

    @classmethod
    def build(
        cls,
        *,
        adapter: EvidenceAdapter,
        plugin: ReaderPlugin,
        client: LLMClient,
        settings: Settings | None = None,
        validators: Sequence[ClaimValidator] = (),
        arbitrator: object | None = None,
        falsifier: Falsifier | None = None,
        reputation_store: InMemoryReputationStore | None = None,
    ) -> ParallaxEngine:
        settings = settings or load_settings()

        ledger = ClaimLedger(validators=validators)
        aggregator = Aggregator(
            ledger, AggregationRules(support_threshold=settings.support_threshold)
        )
        monitor = CoverageMonitor(
            min_support=settings.coverage_min_support,
            min_evidence_fill_rate=settings.min_evidence_fill_rate,
            max_dispute_rate=settings.max_dispute_rate,
        )
        partitioner = BlindPartitioner(
            n_readers=settings.n_readers,
            redundancy=settings.redundancy,
            seed=settings.seed,
        )
        pool = ReaderPool(
            client=client,
            plugin=plugin,
            max_schema_retries=settings.max_schema_retries,
            max_concurrency=settings.max_concurrency,
            temperature=settings.llm_temperature,
            visibility=settings.reader_visibility,
            max_output_tokens=settings.llm_max_output_tokens,
            max_evidence_per_call=settings.max_evidence_per_call,
            max_chars_per_call=settings.llm_max_batch_chars,
        )
        store = reputation_store or InMemoryReputationStore()

        runtime = ParallaxRuntime(
            settings=settings,
            adapter=adapter,
            plugin=plugin,
            pool=pool,
            partitioner=partitioner,
            ledger=ledger,
            aggregator=aggregator,
            monitor=monitor,
            reputation_store=store,
            reputation_policy=ReputationPolicy(store),
            manifest=RunManifest(
                run_id="",
                question="",
                plugin=getattr(plugin, "name", "unknown"),
                seed=settings.seed,
                max_rounds=settings.max_rounds,
                support_threshold=settings.support_threshold,
            ),
            arbitrator=arbitrator if arbitrator is not None else NullArbitrator(),
            falsifier=falsifier,
        )
        return cls(runtime, adapter, plugin)

    # ---- 执行 ----

    async def run(self, question: str, run_id: str | None = None) -> Report:
        """执行一次完整的盲读—聚合—补检循环。

        `run_id` 可以由调用方指定。服务层必须在**提交那一刻**就返回 id
        （那时引擎还没建），如果让引擎自己派生，报告里的 id 就和运行记录里的对不上。
        不指定时按配置派生——CLI 与实验脚本走这条路径，保证同样输入得到同样 id。
        """
        runtime = self.runtime
        resolved_id = run_id or stable_id(
            question,
            runtime.manifest.plugin,
            runtime.settings.seed,
            runtime.settings.n_readers,
            runtime.settings.redundancy,
            runtime.settings.support_threshold,
            runtime.settings.max_rounds,
        )
        runtime.manifest.run_id = resolved_id
        runtime.manifest.question = question

        logger.info("开始运行 %s：%s", resolved_id, question)
        await self._graph.ainvoke({"question": question})

        runtime.manifest.finished_at = datetime.now(UTC)
        return self._build_report(resolved_id, question)

    # ---- 产出 ----

    def _build_report(self, run_id: str, question: str) -> Report:
        runtime = self.runtime
        all_claims = runtime.ledger.claims
        assignments = runtime.manifest.all_assignments()
        groups = runtime.ledger.groups()
        matrix = runtime.monitor.build(
            runtime.ledger.claims,
            {u.evidence_id: u for u in runtime.evidence},
            runtime.rows,
            runtime.cols,
        )

        buckets: dict[ClaimStatus, list[Claim]] = {
            ClaimStatus.HIGH_CONFIDENCE: [],
            ClaimStatus.PENDING: [],
            ClaimStatus.DISPUTED: [],
        }
        for group in groups:
            representative = self._representative(group)
            if representative is not None:
                buckets[group.status].append(representative)

        for claims in buckets.values():
            claims.sort(key=lambda c: (-c.confidence, c.fingerprint))

        independence = build_independence_profile(
            all_claims,
            assignments,
            output_contamination=runtime.output_contamination,
            coverage_fill_rate=matrix.fill_rate(),
            max_evidence_overlap_rate=runtime.settings.max_evidence_overlap_rate,
            min_independent_support=runtime.settings.effective_min_independent_support(),
        )
        return Report(
            run_id=run_id,
            question=question,
            high_confidence=buckets[ClaimStatus.HIGH_CONFIDENCE],
            pending=buckets[ClaimStatus.PENDING],
            disputed=buckets[ClaimStatus.DISPUTED],
            coverage=matrix,
            manifest=runtime.manifest,
            independence=independence,
            provenance=build_provenance_graph(all_claims, assignments, runtime.manifest.receipts),
        )

    def _representative(self, group: LedgerGroup) -> Claim | None:
        """每个指纹取一条代表 claim。

        取「主张该主体且声誉最高」的那条；同分时按 claim_id 排序，
        保证输出可复现（不依赖字典遍历顺序）。
        """
        candidates = [
            c
            for c in (self.runtime.ledger.claim(cid) for cid in group.claim_ids)
            if c is not None and c.polarity == 1
        ]
        if not candidates:
            candidates = [
                c
                for c in (self.runtime.ledger.claim(cid) for cid in group.claim_ids)
                if c is not None
            ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda c: (-c.reputation_at_extraction, c.claim_id))[0]

    def reputation_snapshot(self) -> dict[str, float]:
        return self.runtime.reputation_store.scores()

    def usage_snapshot(self) -> dict[str, int]:
        """调用与 token 用量的合并快照。

        两本账不能合成一本：
        `calls` 由编排层记，语义是"一次 Reader 调用"（池内还会按
        `max_evidence_per_call` 拆成多次 HTTP 请求）；token 只有模型客户端知道。
        早先只读编排层那本，结果报告里出现"12 次调用、0 token"——
        成本正是这个框架对外主张的维度之一，不能是 0。
        """
        usage = self.runtime.usage
        client_usage = getattr(self.runtime.pool.client, "usage", None)
        # 客户端报了就以客户端为准；它没暴露用量时才退回编排层的值
        prompt_tokens = int(getattr(client_usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(client_usage, "completion_tokens", 0) or 0)
        return {
            "calls": usage.calls,
            "failures": usage.failures,
            "schema_retries": usage.schema_retries,
            "prompt_tokens": prompt_tokens or usage.prompt_tokens,
            "completion_tokens": completion_tokens or usage.completion_tokens,
        }
