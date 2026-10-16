"""编排状态与运行时依赖。

状态（State）只放**数据**，运行时对象（账本、聚合器、监控器……）通过闭包注入节点函数。
这么分的原因：状态要能被序列化与检查点化，而账本持有可变引用，
混进状态会让未来的持久化/断点续跑变得非常痛苦。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypedDict

from parallax.config import Settings
from parallax.core.aggregator import Aggregator
from parallax.core.coverage import CoverageDecision, CoverageMonitor
from parallax.core.ledger import ClaimLedger
from parallax.core.partitioning import BlindPartitioner, Partition
from parallax.core.reader_pool import ReaderOutcome, ReaderPool
from parallax.core.reputation import InMemoryReputationStore, ReputationPolicy
from parallax.domain.enums import RoundStopReason
from parallax.domain.models import EvidenceUnit, RunManifest
from parallax.ports.evidence_adapter import EvidenceAdapter
from parallax.ports.llm import Budget, UsageStats
from parallax.ports.reader_plugin import ReaderPlugin

_logger = logging.getLogger(__name__)


class ParallaxState(TypedDict, total=False):
    """编排图的状态。"""

    question: str
    round_index: int
    focus_groups: list[str]
    evidence: list[EvidenceUnit]
    evidence_by_id: dict[str, EvidenceUnit]
    rows: list[str]
    cols: list[str]
    partitions: list[Partition]
    outcomes: list[ReaderOutcome]
    decision: CoverageDecision | None
    stop_reason: RoundStopReason | None


@dataclass
class ParallaxRuntime:
    """一次运行的全部依赖与可变状态。"""

    settings: Settings
    adapter: EvidenceAdapter
    plugin: ReaderPlugin
    pool: ReaderPool
    partitioner: BlindPartitioner
    ledger: ClaimLedger
    aggregator: Aggregator
    monitor: CoverageMonitor
    reputation_store: InMemoryReputationStore
    reputation_policy: ReputationPolicy
    manifest: RunManifest
    fingerprints_seen: set[str] = field(default_factory=set)
    new_fingerprints_last_round: int = 0
    evidence: list[EvidenceUnit] = field(default_factory=list)
    """ingest 阶段加载的证据缓存。

    刻意缓存而不是让各节点自己重读：真实适配器可能读整个代码仓库，
    重复加载既有性能代价，也可能在文件系统变化时产出不一致的结果。
    """
    rows: list[str] = field(default_factory=list)
    cols: list[str] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    usage: UsageStats = field(default_factory=UsageStats)
    arbitrator: object | None = None
    """可选的争议仲裁器（实现 ports.arbitrator.Arbitrator）。
    为 None 时争议组原样保留为 DISPUTED——不猜、不投票、不静默丢弃。"""

    event_sink: Callable[[str, dict], None] | None = None
    """进度事件回调（用于 SSE 推流）。

    刻意做成"退出即失效"的同步回调，而不是把事件塞进编排状态：
    编排图的状态要能被序列化与检查点化，而事件是瞬时副作用，
    混进状态会让未来的持久化/断点续跑变得非常痛苦。
    """

    def emit(self, event_type: str, **payload: object) -> None:
        """发一条进度事件。没有订阅者时是零开销的空操作。"""
        if self.event_sink is None:
            return
        try:
            self.event_sink(event_type, payload)
        except Exception:  # noqa: BLE001 - 推流失败绝不能影响主流程
            _logger.warning("事件回调失败：%s", event_type, exc_info=True)

    def reputation_of(self, agent_id: str) -> float:
        return self.reputation_store.get(agent_id, role="reader").score()

    def record_usage(self, success: bool, schema_retries: int) -> None:
        self.usage.calls += 1
        if not success:
            self.usage.failures += 1
        if schema_retries:
            self.usage.schema_retries += schema_retries

    def budget_exhausted(self) -> bool:
        over_calls = (
            bool(self.settings.max_llm_calls) and self.usage.calls >= self.settings.max_llm_calls
        )
        over_tokens = (
            bool(self.settings.max_tokens) and self.usage.total_tokens >= self.settings.max_tokens
        )
        return over_calls or over_tokens
