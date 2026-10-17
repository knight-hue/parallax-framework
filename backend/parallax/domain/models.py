"""核心领域模型。

设计取舍说明（答辩会被问到的三处）：

1. **Claim 用「指纹 + 极性」而不是自然语言比对来判定同一性。**
   交叉验证的前提是能判定「这是同一条 claim」。用嵌入相似度判定会引入阈值玄学，
   且不可复现。所以指纹由插件给出确定性归一化规则（如 文件:行段:缺陷类），
   极性单独存字段——这样「同主体、反极性」= 矛盾，可以被精确检测而不是概率猜测。

2. **声誉分是 Beta 后验均值，不是加权平均。**
   score = (1 + 命中) / (2 + 命中 + 未命中)，即 Beta(1,1) 先验下的后验均值。
   好处：新 Agent 从 0.5 中性起步、样本少时不会暴涨、无需调参、可解释。

3. **source_refs 是强制的。**
   没有源指针的 claim 不可进入账本——「可追溯」是本框架对外的核心承诺之一。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parallax.domain.enums import ClaimStatus, Polarity, RoundStopReason
from parallax.util import cell_key


def _now() -> datetime:
    return datetime.now(UTC)


class SourceRef(BaseModel):
    """指向原始证据的指针——claim「可追溯」的载体。"""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    adapter: str
    locator: str
    quote: str | None = None


class EvidenceUnit(BaseModel):
    """标准证据单元：不同来源经 EvidenceAdapter 归一化后的统一形态。"""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    adapter: str
    locator: str
    content: str
    content_hash: str = ""
    group: str = "default"
    """所属分组（代码审计里是模块名）。盲读分区默认按 group 切，
    因为让一个 Reader 读到半个文件的片段而不给上下文，会制造假缺陷。"""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditReceipt(BaseModel):
    """一次可审计动作的不可变凭证。

    Receipt 只记录事实，不替代事件流：事件用于进度推送，Receipt 用于最终复盘。
    """

    model_config = ConfigDict(frozen=True)

    protocol_version: str = "parallax.receipt/v1"
    receipt_id: str
    kind: Literal[
        "ingest",
        "partition",
        "reader",
        "claim",
        "coverage",
        "verification",
        "arbitration",
    ]
    run_id: str
    round_index: int = 0
    actor_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=_now)


class Claim(BaseModel):
    """账本条目：一条被结构化记录的主张。"""

    # validate_default 让「source_refs 默认空列表」也走校验，
    # 否则可以靠省略字段绕过「无源指针不入账本」的约束。
    model_config = ConfigDict(validate_default=True)

    claim_id: str
    fingerprint: str
    """主体指纹：判定「是否同一条 claim」的确定性键，由插件给出。"""
    statement: str
    polarity: Polarity = Polarity.ASSERT
    claim_type: str = "generic"
    """插件自定义类型（代码审计里是缺陷类：concurrency / boundary / ...）。"""

    extracted_by: str
    round_index: int = 0
    source_refs: list[SourceRef] = Field(default_factory=list)
    reputation_at_extraction: float = 0.5
    """提取时的 Agent 声誉快照。留快照而非实时值，否则审计时无法复现当时的判定。"""

    verified_by: list[str] = Field(default_factory=list)
    """独立交叉验证过该指纹的 agent_id（由账本回填，去重）。"""
    disputed_with: list[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.PENDING
    confidence: float = 0.0
    trigger_conditions: list[str] = Field(default_factory=list)
    """使主张可被复现/验证的触发条件。旧插件可暂时留空。"""
    counter_conditions: list[str] = Field(default_factory=list)
    """可能推翻主张的边界条件或反证条件。"""
    reproduction_plan: dict[str, Any] = Field(default_factory=dict)
    """可选的最小复现计划；不把自然语言意见误标为已验证。"""
    verification_status: Literal[
        "unverified",
        "confirmed",
        "refuted",
        "insufficient_evidence",
        "reproduced",
        "not_reproduced",
        "fixed",
        "regression_passed",
    ] = "unverified"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_verified(self) -> bool:
        """是否已有外部验证结果；不把 Agent 聚合状态当作事实验证。"""
        return self.verification_status in {
            "confirmed",
            "reproduced",
            "fixed",
            "regression_passed",
        }

    @field_validator("source_refs")
    @classmethod
    def _require_source(cls, v: list[SourceRef]) -> list[SourceRef]:
        # 「无源指针的 claim 不入账本」——这是硬约束，不是约定
        if not v:
            raise ValueError("claim 必须至少携带一个 source_ref")
        return v


class ReputationEvent(BaseModel):
    """声誉变动记录，保留完整轨迹以便复盘。"""

    model_config = ConfigDict(frozen=True)

    run_id: str
    claim_id: str
    outcome: Literal["verified", "refuted", "arbitration_win", "arbitration_loss"]
    at: datetime = Field(default_factory=_now)


class AgentReputation(BaseModel):
    """Agent 历史声誉：跨任务累积，这是「历史声誉分」能被使用的前提。"""

    agent_id: str
    role: str = "reader"
    claims_verified: int = 0
    claims_refuted: int = 0
    arbitration_wins: int = 0
    arbitration_losses: int = 0
    events: list[ReputationEvent] = Field(default_factory=list)

    def score(self) -> float:
        """Beta 后验均值，先验 Beta(1,1)（中性 0.5），值域 (0,1)。"""
        alpha = 1 + self.claims_verified + self.arbitration_wins
        beta = 1 + self.claims_refuted + self.arbitration_losses
        return alpha / (alpha + beta)

    def record(self, run_id: str, claim_id: str, outcome: str) -> None:
        mapping = {
            "verified": "claims_verified",
            "refuted": "claims_refuted",
            "arbitration_win": "arbitration_wins",
            "arbitration_loss": "arbitration_losses",
        }
        attr = mapping[outcome]
        setattr(self, attr, getattr(self, attr) + 1)
        self.events.append(
            ReputationEvent(run_id=run_id, claim_id=claim_id, outcome=outcome)  # type: ignore[arg-type]
        )


class CoverageMatrix(BaseModel):
    """「审视维度 × claim 类型」矩阵——补检闭环的输入。

    行 = 待覆盖的审视维度（代码审计里是模块），列 = claim 类型（缺陷类）。
    稀疏的格子意味着「这个模块的这类问题还没被任何 Reader 覆盖到」。
    """

    rows: list[str] = Field(default_factory=list)
    cols: list[str] = Field(default_factory=list)
    cells: dict[str, int] = Field(default_factory=dict)

    def add(self, row: str, col: str, n: int = 1) -> None:
        if row not in self.rows:
            self.rows.append(row)
        if col not in self.cols:
            self.cols.append(col)
        key = cell_key(row, col)
        self.cells[key] = self.cells.get(key, 0) + n

    def count(self, row: str, col: str) -> int:
        return self.cells.get(cell_key(row, col), 0)

    def total_cells(self) -> int:
        return len(self.rows) * len(self.cols)

    def filled_cells(self, min_support: int = 1) -> int:
        return sum(
            1
            for r in self.rows
            for c in self.cols
            if self.cells.get(cell_key(r, c), 0) >= min_support
        )

    def fill_rate(self, min_support: int = 1) -> float:
        total = self.total_cells()
        return self.filled_cells(min_support) / total if total else 1.0

    def sparse_cells(self, min_support: int = 1) -> list[tuple[str, str]]:
        """未达标格子的清单，按 (行, 列) 稳定排序，保证补检调度可复现。"""
        return sorted(
            (r, c)
            for r in self.rows
            for c in self.cols
            if self.cells.get(cell_key(r, c), 0) < min_support
        )

    def unconfirmed_cells(self, min_support: int = 2) -> list[tuple[str, str]]:
        """「有人报出、但独立来源不足」的格子。

        这是补检**最有价值**的目标：已经存在主张，只是还没获得独立确认。
        必须与「一个 claim 都没有的格子」严格区分——后者通常只反映
        「该模块本来就没有这类缺陷」，盯着它补检只会白烧预算且永不收敛。
        """
        return sorted(
            (r, c)
            for r in self.rows
            for c in self.cols
            if 0 < self.cells.get(cell_key(r, c), 0) < min_support
        )


class RoundRecord(BaseModel):
    """单轮盲读的审计记录。"""

    round_index: int
    assignments: dict[str, list[str]] = Field(default_factory=dict)
    """reader_id -> 该轮分到的 evidence_id 列表。这是「盲读」的取证：
    任意两个 reader 的交集必须为空，可在测试中直接断言。"""
    claims_extracted: int = 0
    new_fingerprints: int = 0
    """本轮**新出现**的主体指纹数——这是补检收敛性的判据。

    只数指纹而不是数 claim：第二轮新 Reader 复核同一问题会产生新 claim_id
    （Agent 不同），但指纹不变，那是「确认」而不是「新发现」。
    用 claim 数判断进展会让循环永不收敛。
    """
    coverage_fill_rate: float = 0.0
    evidence_fill_rate: float = 0.0
    sparse_cell_count: int = 0


class RunManifest(BaseModel):
    """一次运行的完整审计记录——「可复现 / 可审计」的实现载体。"""

    run_id: str
    question: str
    plugin: str
    seed: int
    max_rounds: int
    support_threshold: int
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    rounds: list[RoundRecord] = Field(default_factory=list)
    stop_reason: RoundStopReason | None = None
    total_claims: int = 0
    reader_ids: list[str] = Field(default_factory=list)
    receipts: list[AuditReceipt] = Field(default_factory=list)

    correlation_budget: dict[str, float] = Field(default_factory=dict)
    """本次运行允许的相关性预算快照，便于复现实验口径。"""

    def all_assignments(self) -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}
        for r in self.rounds:
            for reader_id, ev_ids in r.assignments.items():
                merged.setdefault(reader_id, []).extend(ev_ids)
        return merged


class IndependenceProfile(BaseModel):
    """一次运行的独立性画像。

    这里报告的是证据通道的独立程度，不是事实正确率。
    ``effective_channel_count`` 采用有效通道数思想，具体计算由
    ``core.independence`` 完成，并同时给出归一化值避免不同 Reader 数量下误比较。
    """

    reader_count: int = 0
    effective_channel_count: float = 0.0
    normalized_independence: float = 0.0
    evidence_overlap_rate: float = 0.0
    mean_independent_support: float = 0.0
    max_independent_support: int = 0
    output_contamination: bool = False
    isolation_status: Literal["verified", "unknown", "violated"] = "unknown"
    evidence_units: int = 0
    claim_count: int = 0
    claims_with_independent_support: int = 0
    coverage_fill_rate: float = 0.0
    correlation_budget_violated: bool = False
    """是否超过本次运行声明的证据相关性预算。"""
    correlation_budget: dict[str, float] = Field(default_factory=dict)
    """运行时采用的相关性预算快照，便于复现与审计。"""

    @property
    def normalized_channel_ratio(self) -> float:
        """兼容早期草稿的命名。"""
        return self.normalized_independence

    @property
    def evidence_count(self) -> int:
        """兼容早期草稿的命名。"""
        return self.evidence_units

    @property
    def output_contamination_detected(self) -> bool:
        """兼容早期草稿的命名。"""
        return self.output_contamination

    @property
    def claims_total(self) -> int:
        """兼容早期草稿的命名。"""
        return self.claim_count


class ProvenanceNode(BaseModel):
    node_id: str
    node_type: Literal["evidence", "reader", "claim", "coverage", "arbitration", "verification"]
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceEdge(BaseModel):
    source: str
    target: str
    relation: Literal[
        "reviewed_by",
        "produced",
        "derived_from",
        "supports",
        "contradicts",
        "covers",
        "verified_by",
        "arbitrated_by",
    ]


class ProvenanceGraph(BaseModel):
    """可序列化的证据血缘图；先用 JSON 表达，不引入图数据库依赖。"""

    nodes: list[ProvenanceNode] = Field(default_factory=list)
    edges: list[ProvenanceEdge] = Field(default_factory=list)


# 早期升级草稿曾使用 Lineage 命名。类型别名保留兼容性，不复制领域模型。
LineageNode = ProvenanceNode
LineageEdge = ProvenanceEdge
EvidenceLineage = ProvenanceGraph


class Report(BaseModel):
    """最终产出：按聚合结论分桶。"""

    run_id: str
    question: str
    high_confidence: list[Claim] = Field(default_factory=list)
    pending: list[Claim] = Field(default_factory=list)
    disputed: list[Claim] = Field(default_factory=list)
    coverage: CoverageMatrix = Field(default_factory=CoverageMatrix)
    manifest: RunManifest
    independence: IndependenceProfile = Field(default_factory=IndependenceProfile)
    provenance: ProvenanceGraph = Field(default_factory=ProvenanceGraph)

    @property
    def lineage(self) -> EvidenceLineage:
        """兼容早期升级草稿中的 `lineage` 命名。"""
        return self.provenance

    def counts(self) -> dict[str, int]:
        return {
            "high_confidence": len(self.high_confidence),
            "pending": len(self.pending),
            "disputed": len(self.disputed),
        }
