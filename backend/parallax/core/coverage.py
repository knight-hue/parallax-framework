"""覆盖率监控：机制 4「覆盖率驱动补检」的实现。

## 为什么这一层必须在系统层，而不能交给 Reader

Reader 只知道自己的那片证据，它**无从知道全局缺口**——这正是它能保持独立的原因。
所以缺口发现必须由系统层完成：算子「审视维度 × claim 类型」矩阵，找出稀疏格。

## 关键设计：补检派的是「新」Reader

发现缺口后，框架**不会**去问原来的 Reader「你漏了这块，再看一眼」——
那样等于把结论先行的偏见请回来。正确做法是：调度一批**全新的 Reader**
（新身份、新分区）去定向收集稀疏区域的证据。所以老 Reader 的盲读状态
从头到尾没有被破坏。

这与 partitioner 里「每轮生成全新 reader_id」是同一件事的两端。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field

from parallax.core.scheduling import AdaptiveFocusScheduler
from parallax.domain.enums import RoundStopReason
from parallax.domain.models import Claim, CoverageMatrix, EvidenceUnit
from parallax.util import cell_key, split_cell_key


class CoverageDecision(BaseModel):
    """覆盖率的研判结论，驱动编排图的循环边。

    ## 为什么有两个覆盖率

    「覆盖率」在本框架里其实是两件事，混为一谈会导致补检永不收敛：

    **证据覆盖率**（evidence_fill_rate）
        有多少条证据被 >= min_support 个独立 Reader 看过。这是**硬要求**，
        衡量的是「证据完备性」——有没有哪个模块压根没被足够多的人看过。

    **claim 格填充率**（claim_cell_fill_rate）
        「模块 × 缺陷类」矩阵里有多少格有了 claim。这是**软信号，不能当停止条件**：
        多数模块不可能同时具备全部 8 类缺陷，要求它填满 100% 只会让补检永远跑不完。
        它的正确用途是**指路**——告诉系统下一轮该重点复核哪些格。

    所以停止条件是「证据覆盖达标 且 上一轮无新增」，而不是「矩阵填满」。
    """

    should_retrieve: bool
    focus_groups: list[str] = Field(default_factory=list)
    stop_reason: RoundStopReason | None = None
    evidence_fill_rate: float = 0.0
    claim_cell_fill_rate: float = 0.0
    uncovered_rows: list[str] = Field(default_factory=list)
    sparse_cells: list[tuple[str, str]] = Field(default_factory=list)
    dispute_rate: float = 0.0

    @property
    def reason_text(self) -> str:
        if self.should_retrieve:
            return (
                f"证据覆盖 {self.evidence_fill_rate:.0%}，"
                f"待复核维度 {len(self.uncovered_rows)} 个、格子 {len(self.sparse_cells)} 个"
            )
        return f"停止：{self.stop_reason.value if self.stop_reason else 'unknown'}"


class CoverageMonitor:
    """覆盖率监控器。"""

    def __init__(
        self,
        min_support: int = 1,
        min_evidence_fill_rate: float = 1.0,
        max_dispute_rate: float = 0.5,
        adaptive_scheduler: AdaptiveFocusScheduler | None = None,
    ) -> None:
        self.min_support = min_support
        self.min_evidence_fill_rate = min_evidence_fill_rate
        self.max_dispute_rate = max_dispute_rate
        self.adaptive_scheduler = adaptive_scheduler

    def build(
        self,
        claims: Sequence[Claim],
        evidence_by_id: Mapping[str, EvidenceUnit],
        rows: Sequence[str],
        cols: Sequence[str],
    ) -> CoverageMatrix:
        """构造覆盖率矩阵。

        单元格取值 = 该 (维度, 类型) 上**独立 Agent 的个数**，不是 claim 条数。
        这样「同一个 Agent 重复报同一格」不会把格子填满，与交叉验证的语义保持一致。

        行与列都预先铺满：一个**没有任何 claim 的模块**才是最该被发现的缺口，
        如果只按已有 claim 建矩阵，这种最严重的空洞反而会被漏掉。
        """
        matrix = CoverageMatrix(rows=list(rows), cols=list(cols))
        agents_per_cell: dict[str, set[str]] = {}
        for claim in claims:
            for ref in claim.source_refs:
                unit = evidence_by_id.get(ref.evidence_id)
                if unit is None:
                    continue
                key = cell_key(unit.group, claim.claim_type)
                agents_per_cell.setdefault(key, set()).add(claim.extracted_by)
        for key in sorted(agents_per_cell):
            row, col = split_cell_key(key)
            matrix.add(row, col, len(agents_per_cell[key]))
        return matrix

    def evidence_fill_rate(
        self,
        assignments: Mapping[str, Sequence[str]],
        evidence_ids: Sequence[str],
        min_support: int | None = None,
    ) -> float:
        """被 >= min_support 个独立 Reader 看过的证据占比。

        `assignments` 是 reader_id -> evidence_id 列表的累积映射。
        Reader 身份是轮次隔离的，所以重复轮次不会被误算成"同一个 Agent 又看了一遍"。
        """
        counts = self._read_counts(assignments)
        if not evidence_ids:
            return 1.0
        support = self.min_support if min_support is None else min_support
        covered = sum(1 for eid in evidence_ids if counts[eid] >= support)
        return covered / len(evidence_ids)

    def row_support(
        self,
        assignments: Mapping[str, Sequence[str]],
        units: Mapping[str, EvidenceUnit],
        rows: Sequence[str],
        min_support: int | None = None,
    ) -> tuple[dict[str, int], list[str]]:
        """每个审视维度的支撑度，以及未达标维度的清单。

        取该维度下证据被阅读次数的**最小值**而非平均：
        一个模块 20 个文件、19 个被看两次、1 个只看了一次，
        不该算「这个模块覆盖达标」——那个只被看一次的文件恰恰最可能藏缺陷。
        """
        support = self.min_support if min_support is None else min_support
        counts = self._read_counts(assignments)
        by_group: dict[str, list[str]] = {}
        for eid, unit in units.items():
            by_group.setdefault(unit.group, []).append(eid)

        per_row: dict[str, int] = {}
        for row in rows:
            eids = by_group.get(row, [])
            per_row[row] = min((counts[eid] for eid in eids), default=0)
        uncovered = sorted(r for r, s in per_row.items() if s < support)
        return per_row, uncovered

    @staticmethod
    def _read_counts(assignments: Mapping[str, Sequence[str]]) -> Counter:
        counts: Counter = Counter()
        for eids in assignments.values():
            for eid in set(eids):
                counts[eid] += 1
        return counts

    def decide(
        self,
        matrix: CoverageMatrix,
        *,
        round_index: int,
        max_rounds: int,
        evidence_fill_rate: float = 1.0,
        uncovered_rows: Sequence[str] = (),
        budget_exhausted: bool = False,
        dispute_rows: Sequence[str] = (),
        new_fingerprints_last_round: int | None = None,
    ) -> CoverageDecision:
        """判断是否继续补检。

        停止条件（按优先级）：
            预算耗尽 > 轮次用尽 > 上一轮无新增指纹 > 无值得补检的目标
        """
        claim_fill = matrix.fill_rate(self.min_support)
        unconfirmed = matrix.unconfirmed_cells(self.min_support)
        sparse = matrix.sparse_cells(self.min_support)
        dispute_rate = self._dispute_rate(matrix, dispute_rows)

        def verdict(
            should: bool,
            reason: RoundStopReason | None,
            focus: list[str] | None = None,
        ) -> CoverageDecision:
            return CoverageDecision(
                should_retrieve=should,
                focus_groups=focus or [],
                stop_reason=reason,
                evidence_fill_rate=round(evidence_fill_rate, 4),
                claim_cell_fill_rate=round(claim_fill, 4),
                uncovered_rows=list(uncovered_rows),
                sparse_cells=sparse,
                dispute_rate=round(dispute_rate, 4),
            )

        if budget_exhausted:
            return verdict(False, RoundStopReason.BUDGET_EXHAUSTED)
        if round_index + 1 >= max_rounds:
            return verdict(False, RoundStopReason.MAX_ROUNDS_REACHED)
        if round_index > 0 and new_fingerprints_last_round == 0:
            # 补检了一轮却一条新主体都没发现 → 说明已经查透，继续只是烧钱
            return verdict(False, RoundStopReason.NO_NEW_EVIDENCE)

        focus: list[str] = []
        trigger: list[str] = []

        # ① 证据覆盖不足 —— 硬触发条件
        #    「某些证据没有被足够多个独立 Reader 看过」是可判定、可收敛的缺口。
        if evidence_fill_rate < self.min_evidence_fill_rate:
            trigger.extend(uncovered_rows)

        # ② 存在争议 —— 硬触发条件
        #    争议意味着结论未定，需要更多独立证据来决断。
        for row in dispute_rows:
            if row not in trigger:
                trigger.append(row)

        # ③ 有人报出但无人确认的格子 —— **仅作聚焦提示，不单独触发**
        #    单独拿它触发会让补检永不收敛：多数模块本来就不会具备全部缺陷类型，
        #    那些格子永远凑不满 min_support，于是每一轮都能找到「新的待确认项」。
        for row, _col in unconfirmed:
            if row not in focus:
                focus.append(row)

        if not trigger:
            return verdict(False, RoundStopReason.COVERAGE_SATISFIED)

        for row in trigger:
            if row not in focus:
                focus.append(row)
        if self.adaptive_scheduler is not None:
            unconfirmed_rows = [row for row, _ in unconfirmed]
            focus_set = set(focus)
            ranked = self.adaptive_scheduler.rank(
                focus,
                uncovered_rows=uncovered_rows,
                dispute_rows=dispute_rows,
                unconfirmed_rows=unconfirmed_rows,
            )
            focus = [row for row in ranked if row in focus_set]
        return verdict(True, None, focus)

    @staticmethod
    def _dispute_rate(matrix: CoverageMatrix, dispute_rows: Sequence[str]) -> float:
        if not matrix.rows:
            return 0.0
        involved = {r for r in dispute_rows if r}
        return len(involved) / len(matrix.rows)
