"""LangGraph 编排图。

     START
       │
    ingest          证据适配器 → 标准 EvidenceUnit
       │
    partition       按当前轮次切出各 Reader 的分区（第一轮全域；补检轮只切稀疏分组）
       │
    [有空分区?]──是──► finalize
       │否
    blind_read      N 个 Reader 并发盲读（互不可见）
       │
    collect         校验并写入 Claim 账本
       │
    aggregate       规则化聚合：高置信 / 待验证 / 争议（+ 声誉结算）
       │
    coverage        构造覆盖率矩阵并研判是否继续补检
       │
    [需要补检?]──是──► partition（round_index+1，全新 Reader）
       │否
    finalize        产出 Report
       │
      END

两个关键点都体现在图上：

1. **盲读在 Reader 层**：`blind_read` 收到的只有 `partitions`，看不到账本。
2. **覆盖率在系统层**：只有 `coverage` 节点能看到全局矩阵，并由它决定是否派新 Reader。
   回到 `partition` 时 `round_index` 已 +1，于是 `reader_ids()` 生成的是**全新身份**——
   老 Reader 不会被要求补读，它的盲读状态从头到尾没被破坏。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph

from parallax.core.independence import evidence_overlap_rate
from parallax.domain.enums import ClaimStatus, RoundStopReason
from parallax.domain.models import EvidenceUnit, RoundRecord
from parallax.graph.state import ParallaxRuntime, ParallaxState

logger = logging.getLogger(__name__)


def build_graph(runtime: ParallaxRuntime):
    """构建并编译编排图。"""

    # ---- 节点 ----

    async def ingest(state: ParallaxState) -> ParallaxState:
        """加载证据并铺满覆盖率矩阵的行列维度。"""
        question = state["question"]
        evidence = runtime.adapter.load(question)
        rows = runtime.adapter.dimension_rows(evidence)
        cols = runtime.plugin.claim_types()
        if not rows:
            # 适配器没给出维度时退化为「按分组的出现顺序」
            rows = sorted({u.group for u in evidence})
        runtime.manifest.reader_ids = []
        runtime.manifest.rounds = []
        runtime.evidence = evidence
        runtime.rows = rows
        runtime.cols = cols

        initial_focus: list[str] = []
        count = runtime.settings.initial_focus_count
        if count > 0:
            initial_focus = list(rows[:count])
            logger.info("ingest: 首轮按预算限制为 %d 个维度 %s", count, initial_focus)

        runtime.emit(
            "ingest",
            evidence_count=len(evidence),
            module_count=len(rows),
            claim_type_count=len(cols),
            modules=rows,
        )
        runtime.record_receipt(
            "ingest",
            evidence_ids=[unit.evidence_id for unit in evidence],
            payload={"question": question, "rows": rows, "cols": cols},
        )
        logger.info(
            "ingest: %d 条证据 / %d 个审视维度 / %d 个 claim 类型",
            len(evidence),
            len(rows),
            len(cols),
        )
        return {
            "evidence": evidence,
            "evidence_by_id": {u.evidence_id: u for u in evidence},
            "rows": rows,
            "cols": cols,
            "round_index": 0,
            "focus_groups": initial_focus,
        }

    async def partition(state: ParallaxState) -> ParallaxState:
        """切分本轮证据。"""
        round_index = state.get("round_index", 0)
        focus = state.get("focus_groups") or None
        partitions = runtime.partitioner.partition(
            state.get("evidence", []),
            round_index=round_index,
            focus_groups=focus,
        )
        non_empty = [p for p in partitions if p.units]
        if not non_empty:
            # 定向补检时找不到任何证据 → 没有新证据可读，正常收敛而不是死循环
            logger.info("partition: 第 %d 轮无可用证据，停止补检", round_index)
            return {"partitions": [], "stop_reason": RoundStopReason.NO_NEW_EVIDENCE}

        for p in non_empty:
            if p.reader_id not in runtime.manifest.reader_ids:
                runtime.manifest.reader_ids.append(p.reader_id)
        logger.info(
            "partition: 第 %d 轮 %d 个 Reader（focus=%s）",
            round_index,
            len(non_empty),
            focus or "全域",
        )
        runtime.emit(
            "partition",
            round=round_index,
            readers=[
                {"reader_id": p.reader_id, "files": len(p.units), "groups": p.groups}
                for p in non_empty
            ],
            focus=focus or [],
        )
        runtime.record_receipt(
            "partition",
            round_index=round_index,
            evidence_ids=[unit.evidence_id for partition in non_empty for unit in partition.units],
            payload={
                "readers": [partition.reader_id for partition in non_empty],
                "focus": focus or [],
            },
        )
        return {"partitions": non_empty, "stop_reason": None}

    async def blind_read(state: ParallaxState) -> ParallaxState:
        """并发盲读。每个 Reader 只拿到自己的分区。"""
        outcomes = await runtime.pool.run_round(
            state["partitions"],
            question=state["question"],
            reputation_lookup=runtime.reputation_of,
            usage_hook=runtime.record_usage,
        )
        for outcome in outcomes:
            runtime.emit(
                "reader",
                round=outcome.round_index,
                reader_id=outcome.reader_id,
                files=len(outcome.evidence_ids),
                claims=len(outcome.claims),
                ok=outcome.ok,
                error=outcome.error,
                saw_prior_claims=outcome.saw_prior_claims,
            )
            runtime.record_receipt(
                "reader",
                round_index=outcome.round_index,
                actor_id=outcome.reader_id,
                evidence_ids=outcome.evidence_ids,
                claim_ids=[claim.claim_id for claim in outcome.claims],
                payload={"ok": outcome.ok, "error": outcome.error},
            )
        runtime.output_contamination = runtime.output_contamination or any(
            outcome.saw_prior_claims > 0 for outcome in outcomes
        )
        return {"outcomes": outcomes}

    async def collect(state: ParallaxState) -> ParallaxState:
        """准入校验后写入账本。"""
        shard_by_reader = {p.reader_id: list(p.units) for p in state["partitions"]}
        admitted = 0
        for outcome in state.get("outcomes", []):
            shard = shard_by_reader.get(outcome.reader_id, [])
            for claim in outcome.claims:
                if runtime.ledger.admit(claim, shard) is not None:
                    admitted += 1
        record = RoundRecord(
            round_index=state.get("round_index", 0),
            assignments={p.reader_id: p.evidence_ids for p in state["partitions"]},
            claims_extracted=admitted,
        )
        runtime.manifest.rounds = [
            r for r in runtime.manifest.rounds if r.round_index != record.round_index
        ] + [record]
        runtime.manifest.rounds.sort(key=lambda r: r.round_index)
        runtime.emit(
            "collect",
            round=record.round_index,
            admitted=admitted,
            ledger_size=len(runtime.ledger),
            rejected=len(runtime.ledger.rejections),
        )
        runtime.record_receipt(
            "claim",
            round_index=record.round_index,
            claim_ids=[claim.claim_id for claim in runtime.ledger.claims],
            payload={"admitted": admitted, "rejected": len(runtime.ledger.rejections)},
        )
        return {}

    async def verify(state: ParallaxState) -> ParallaxState:
        """执行可选的独立反证；结果只写入验证状态，不参与多数票聚合。"""
        falsifier = runtime.falsifier
        if falsifier is None:
            return {}
        results = []
        current_claims = [
            claim
            for outcome in state.get("outcomes", [])
            for claim in outcome.claims
            if runtime.ledger.claim(claim.claim_id) is not None
        ]
        evidence = list(runtime.evidence)
        for claim in current_claims:
            result = falsifier.evaluate(claim, evidence)
            claim.verification_status = result.verdict
            claim.metadata["falsifier"] = getattr(falsifier, "name", type(falsifier).__name__)
            claim.metadata["verification_evidence_ids"] = list(result.evidence_ids)
            claim.metadata["verification_reason"] = result.reason
            results.append(
                {
                    "claim_id": claim.claim_id,
                    "verdict": result.verdict,
                    "evidence_ids": result.evidence_ids,
                    "reason": result.reason,
                }
            )
        runtime.emit("verification", round=state.get("round_index", 0), results=results)
        runtime.record_receipt(
            "verification",
            round_index=state.get("round_index", 0),
            claim_ids=[item["claim_id"] for item in results],
            evidence_ids=sorted({e for item in results for e in item["evidence_ids"]}),
            payload={
                "falsifier": getattr(falsifier, "name", type(falsifier).__name__),
                "results": results,
            },
        )
        return {}

    async def aggregate(state: ParallaxState) -> ParallaxState:
        """规则化聚合 + 声誉结算。"""
        overlap_rate = evidence_overlap_rate(runtime.manifest.all_assignments())
        runtime.correlation_budget_violated = runtime.output_contamination or overlap_rate > max(
            0.0, min(1.0, runtime.settings.max_evidence_overlap_rate)
        )
        runtime.manifest.correlation_budget = {
            "max_evidence_overlap_rate": max(
                0.0, min(1.0, runtime.settings.max_evidence_overlap_rate)
            ),
            "min_independent_support": float(runtime.settings.effective_min_independent_support()),
        }
        groups = runtime.aggregator.sweep()
        if runtime.correlation_budget_violated:
            _downgrade_budget_violations(runtime, groups)
        runtime.reputation_policy.apply_cross_validation(
            groups, runtime.ledger, runtime.manifest.run_id
        )

        if runtime.arbitrator is not None:
            await _arbitrate_disputes(runtime, groups)
            # 仲裁会改写状态与声誉，因此重算一次，避免把陈旧结论写进本轮记录
            groups = runtime.aggregator.sweep()
            if runtime.correlation_budget_violated:
                _downgrade_budget_violations(runtime, groups)

        current_fingerprints = {g.fingerprint for g in groups}
        runtime.new_fingerprints_last_round = len(current_fingerprints - runtime.fingerprints_seen)
        runtime.fingerprints_seen = current_fingerprints

        if runtime.manifest.rounds:
            record = runtime.manifest.rounds[-1]
            record.claims_extracted = len(runtime.ledger)
            record.new_fingerprints = runtime.new_fingerprints_last_round

        by_status: dict[str, int] = {}
        for group in groups:
            by_status[group.status.value] = by_status.get(group.status.value, 0) + 1
        runtime.emit(
            "aggregate",
            round=state.get("round_index", 0),
            new_fingerprints=runtime.new_fingerprints_last_round,
            by_status=by_status,
            ledger_size=len(runtime.ledger),
        )
        return {}

    async def coverage(state: ParallaxState) -> ParallaxState:
        """构造覆盖率矩阵并研判是否补检。"""
        evidence_by_id = state.get("evidence_by_id", {})
        rows = state.get("rows", [])
        matrix = runtime.monitor.build(
            runtime.ledger.claims, evidence_by_id, rows, state.get("cols", [])
        )

        assignments = runtime.manifest.all_assignments()
        evidence_fill = runtime.monitor.evidence_fill_rate(assignments, list(evidence_by_id.keys()))
        _support_by_row, uncovered_rows = runtime.monitor.row_support(
            assignments, evidence_by_id, rows
        )

        decision = runtime.monitor.decide(
            matrix,
            round_index=state.get("round_index", 0),
            max_rounds=runtime.settings.max_rounds,
            evidence_fill_rate=evidence_fill,
            uncovered_rows=uncovered_rows,
            budget_exhausted=runtime.budget_exhausted(),
            dispute_rows=_dispute_rows(runtime, evidence_by_id),
            new_fingerprints_last_round=runtime.new_fingerprints_last_round,
        )
        if runtime.manifest.rounds:
            current = runtime.manifest.rounds[-1]
            current.coverage_fill_rate = decision.claim_cell_fill_rate
            current.evidence_fill_rate = decision.evidence_fill_rate
            current.sparse_cell_count = len(decision.sparse_cells)

        logger.info("coverage: %s", decision.reason_text)
        runtime.emit(
            "coverage",
            round=state.get("round_index", 0),
            should_retrieve=decision.should_retrieve,
            evidence_fill_rate=decision.evidence_fill_rate,
            claim_cell_fill_rate=decision.claim_cell_fill_rate,
            uncovered_rows=decision.uncovered_rows,
            sparse_cell_count=len(decision.sparse_cells),
            dispute_rate=decision.dispute_rate,
            stop_reason=decision.stop_reason.value if decision.stop_reason else None,
            focus_groups=decision.focus_groups,
        )
        runtime.record_receipt(
            "coverage",
            round_index=state.get("round_index", 0),
            payload={
                "should_retrieve": decision.should_retrieve,
                "evidence_fill_rate": decision.evidence_fill_rate,
                "claim_cell_fill_rate": decision.claim_cell_fill_rate,
                "stop_reason": decision.stop_reason.value if decision.stop_reason else None,
            },
        )

        if not decision.should_retrieve:
            return {"decision": decision, "stop_reason": decision.stop_reason}
        # 继续补检：轮次 +1，让 partitioner 生成全新的 Reader 身份
        return {
            "decision": decision,
            "focus_groups": decision.focus_groups,
            "round_index": state.get("round_index", 0) + 1,
        }

    async def finalize(state: ParallaxState) -> ParallaxState:
        """收敛并落定 manifest 的收尾字段。"""
        stop_reason = state.get("stop_reason")
        if stop_reason is None:
            decision = state.get("decision")
            stop_reason = decision.stop_reason if decision else RoundStopReason.COVERAGE_SATISFIED

        runtime.aggregator.sweep()
        groups = runtime.ledger.groups()
        if runtime.correlation_budget_violated:
            _downgrade_budget_violations(runtime, groups)
        high = sum(1 for g in groups if g.status.value == "high_confidence")
        pending = sum(1 for g in groups if g.status.value == "pending")
        disputed = sum(1 for g in groups if g.status.value == "disputed")

        runtime.manifest.stop_reason = _resolve_stop_reason(runtime, stop_reason)
        runtime.manifest.total_claims = len(runtime.ledger)
        logger.info(
            "finalize: 高置信 %d / 待验证 %d / 争议 %d（停止原因 %s）",
            high,
            pending,
            disputed,
            runtime.manifest.stop_reason,
        )
        runtime.emit(
            "finalize",
            high_confidence=high,
            pending=pending,
            disputed=disputed,
            total_claims=runtime.manifest.total_claims,
            rounds=len(runtime.manifest.rounds),
            stop_reason=runtime.manifest.stop_reason.value
            if runtime.manifest.stop_reason
            else None,
        )
        return {}

    def route_after_partition(state: ParallaxState) -> str:
        return "finalize" if state.get("stop_reason") else "blind_read"

    def route_after_coverage(state: ParallaxState) -> str:
        decision = state.get("decision")
        if decision is not None and decision.should_retrieve and not state.get("stop_reason"):
            return "partition"
        return "finalize"

    # ---- 组图 ----

    graph = StateGraph(ParallaxState)
    graph.add_node("ingest", ingest)
    graph.add_node("partition", partition)
    graph.add_node("blind_read", blind_read)
    graph.add_node("collect", collect)
    graph.add_node("verify", verify)
    graph.add_node("aggregate", aggregate)
    graph.add_node("coverage", coverage)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "partition")
    graph.add_conditional_edges(
        "partition", route_after_partition, {"blind_read": "blind_read", "finalize": "finalize"}
    )
    graph.add_edge("blind_read", "collect")
    graph.add_edge("collect", "verify")
    graph.add_edge("verify", "aggregate")
    graph.add_edge("aggregate", "coverage")
    graph.add_conditional_edges(
        "coverage", route_after_coverage, {"partition": "partition", "finalize": "finalize"}
    )
    graph.add_edge("finalize", END)

    return graph.compile()


# ---- 辅助 ----


def _resolve_stop_reason(
    runtime: ParallaxRuntime, fallback: RoundStopReason | None
) -> RoundStopReason:
    """把「预算耗尽」的判定也反映到停止原因上，便于实验归因。"""
    if runtime.budget_exhausted():
        return RoundStopReason.BUDGET_EXHAUSTED
    return fallback or RoundStopReason.COVERAGE_SATISFIED


def _downgrade_budget_violations(runtime: ParallaxRuntime, groups: list) -> None:
    """相关性预算超限时，禁止自动把重复意见标成高置信。"""
    threshold = runtime.settings.effective_min_independent_support()
    for group in groups:
        if group.status != ClaimStatus.HIGH_CONFIDENCE:
            continue
        if group.cross_validation_count < threshold:
            continue
        group.status = ClaimStatus.PENDING
        for claim_id in group.claim_ids:
            claim = runtime.ledger.claim(claim_id)
            if claim is not None:
                claim.status = ClaimStatus.PENDING


def _dispute_rows(
    runtime: ParallaxRuntime, evidence_by_id: Mapping[str, EvidenceUnit]
) -> list[str]:
    """争议 claim 涉及的审视维度（覆盖率监控据此把争议也纳入补检目标）。"""
    rows: list[str] = []
    for group in runtime.aggregator.arbitration_queue():
        for claim_id in group.claim_ids:
            claim = runtime.ledger.claim(claim_id)
            if claim is None:
                continue
            for ref in claim.source_refs:
                unit = evidence_by_id.get(ref.evidence_id)
                if unit is not None and unit.group not in rows:
                    rows.append(unit.group)
    return rows


async def _arbitrate_disputes(runtime: ParallaxRuntime, groups: list) -> None:
    """对争议组执行仲裁（仅当注入了仲裁器）。"""
    arbitrator = runtime.arbitrator
    if arbitrator is None:
        return
    for group in runtime.aggregator.arbitration_queue(groups):
        verdict = await arbitrator.arbitrate(  # type: ignore[attr-defined]
            group,
            [c for c in (runtime.ledger.claim(cid) for cid in group.claim_ids) if c is not None],
        )
        runtime.aggregator.apply_arbitration(group, verdict)
        runtime.reputation_policy.apply_arbitration(
            group, runtime.ledger, runtime.manifest.run_id, verdict
        )
        runtime.record_receipt(
            "arbitration",
            claim_ids=list(group.claim_ids),
            payload={"fingerprint": group.fingerprint, "status": verdict.value},
        )
