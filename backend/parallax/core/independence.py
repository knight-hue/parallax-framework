"""独立性运行时画像与证据血缘构建。

该模块只消费已经落账的 Claim 和分区取证，不参与结论裁决。
因此它不会把"多个 Agent 说了一样的话"误写成"事实正确"，而是报告：
这些意见是否来自不同证据路径、彼此重叠多少、是否满足输出隔离条件。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from parallax.domain.models import (
    Claim,
    IndependenceProfile,
    ProvenanceEdge,
    ProvenanceGraph,
    ProvenanceNode,
)


def _effective_channel_count(assignments: Mapping[str, list[str]]) -> float:
    readers = sorted(assignments)
    if not readers:
        return 0.0
    # 用 Jaccard 重叠构造相关性 Gram 矩阵。对角线为 1，空分区不算 Reader。
    active = [r for r in readers if assignments[r]]
    if not active:
        return 0.0
    gram: list[list[float]] = []
    sets = [set(assignments[r]) for r in active]
    for left in sets:
        row = []
        for right in sets:
            union = left | right
            row.append(len(left & right) / len(union) if union else 0.0)
        gram.append(row)
    trace = float(len(gram))
    trace_square = sum(value * value for row in gram for value in row)
    return (trace * trace / trace_square) if trace_square else 0.0


def evidence_overlap_rate(assignments: Mapping[str, list[str]]) -> float:
    """计算活跃 Reader 两两证据分区的平均 Jaccard 重叠。"""
    active = [set(evidence) for evidence in assignments.values() if evidence]
    pairs: list[float] = []
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            union = left | right
            pairs.append(len(left & right) / len(union) if union else 0.0)
    return round(sum(pairs) / len(pairs), 6) if pairs else 0.0


def build_independence_profile(
    claims: Iterable[Claim],
    assignments: Mapping[str, list[str]],
    *,
    output_contamination: bool = False,
    coverage_fill_rate: float = 0.0,
    max_evidence_overlap_rate: float = 1.0,
    min_independent_support: int = 0,
) -> IndependenceProfile:
    claims = list(claims)
    active = {reader: set(evidence) for reader, evidence in assignments.items() if evidence}
    overlap_rate = evidence_overlap_rate(assignments)
    effective = _effective_channel_count(assignments)
    reader_count = len(active)
    by_subject: dict[tuple[str, object], set[str]] = defaultdict(set)
    for claim in claims:
        # 以指纹和极性分开统计，避免把反方意见误算成正方支持。
        by_subject[(claim.fingerprint, claim.polarity)].add(claim.extracted_by)
    support = [
        len(set(claim.verified_by) or by_subject[(claim.fingerprint, claim.polarity)])
        for claim in claims
    ]
    claims_with_support = sum(value >= 2 for value in support)
    isolation_status = (
        "violated" if output_contamination else ("verified" if reader_count else "unknown")
    )
    correlation_budget_violated = output_contamination or overlap_rate > max(
        0.0, min(1.0, max_evidence_overlap_rate)
    )
    return IndependenceProfile(
        reader_count=reader_count,
        effective_channel_count=round(effective, 6),
        normalized_independence=round(effective / reader_count, 6) if reader_count else 0.0,
        evidence_overlap_rate=overlap_rate,
        mean_independent_support=round(sum(support) / len(support), 6) if support else 0.0,
        max_independent_support=max(support, default=0),
        output_contamination=output_contamination,
        isolation_status=isolation_status,
        evidence_units=len({evidence for values in assignments.values() for evidence in values}),
        claim_count=len(claims),
        claims_with_independent_support=claims_with_support,
        coverage_fill_rate=round(max(0.0, min(1.0, coverage_fill_rate)), 6),
        correlation_budget_violated=correlation_budget_violated,
        correlation_budget={
            "max_evidence_overlap_rate": max(0.0, min(1.0, max_evidence_overlap_rate)),
            "min_independent_support": float(max(0, min_independent_support)),
        },
    )


def build_provenance_graph(
    claims: Iterable[Claim],
    assignments: Mapping[str, list[str]],
    receipts: Iterable[object] = (),
) -> ProvenanceGraph:
    claims = list(claims)
    nodes: dict[str, ProvenanceNode] = {}
    edges: set[tuple[str, str, str]] = set()

    for reader_id, evidence_ids in assignments.items():
        reader_node = f"reader:{reader_id}"
        nodes[reader_node] = ProvenanceNode(
            node_id=reader_node, node_type="reader", label=reader_id
        )
        for evidence_id in evidence_ids:
            evidence_node = f"evidence:{evidence_id}"
            nodes.setdefault(
                evidence_node,
                ProvenanceNode(node_id=evidence_node, node_type="evidence", label=evidence_id),
            )
            edges.add((evidence_node, reader_node, "reviewed_by"))

    by_fingerprint: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        claim_node = f"claim:{claim.claim_id}"
        nodes[claim_node] = ProvenanceNode(
            node_id=claim_node, node_type="claim", label=claim.statement
        )
        reader_node = f"reader:{claim.extracted_by}"
        edges.add((reader_node, claim_node, "produced"))
        for ref in claim.source_refs:
            edges.add((f"evidence:{ref.evidence_id}", claim_node, "derived_from"))
        by_fingerprint[claim.fingerprint].append(claim)

    for group in by_fingerprint.values():
        for left in group:
            for right in group:
                if left.claim_id == right.claim_id:
                    continue
                relation = "supports" if left.polarity == right.polarity else "contradicts"
                edges.add((f"claim:{left.claim_id}", f"claim:{right.claim_id}", relation))

    for claim in claims:
        if claim.verification_status != "unverified":
            verification_node = f"verification:{claim.claim_id}"
            nodes[verification_node] = ProvenanceNode(
                node_id=verification_node,
                node_type="verification",
                label=claim.verification_status,
                metadata={
                    "status": claim.verification_status,
                    "evidence_ids": claim.metadata.get("verification_evidence_ids", []),
                    "falsifier": claim.metadata.get("falsifier"),
                },
            )
            edges.add((verification_node, f"claim:{claim.claim_id}", "verified_by"))

    for receipt in receipts:
        if getattr(receipt, "kind", None) != "arbitration":
            continue
        receipt_id = getattr(receipt, "receipt_id", "")
        if not receipt_id:
            continue
        node_id = f"arbitration:{receipt_id}"
        payload = dict(getattr(receipt, "payload", {}) or {})
        nodes[node_id] = ProvenanceNode(
            node_id=node_id,
            node_type="arbitration",
            label=str(payload.get("status", "")),
            metadata=payload,
        )
        for claim_id in getattr(receipt, "claim_ids", []) or []:
            edges.add((node_id, f"claim:{claim_id}", "arbitrated_by"))

    return ProvenanceGraph(
        nodes=sorted(nodes.values(), key=lambda node: node.node_id),
        edges=[ProvenanceEdge(source=s, target=t, relation=r) for s, t, r in sorted(edges)],
    )
