"""独立性运行时画像与证据血缘构建。

该模块只消费已经落账的 Claim 和分区取证，不参与结论裁决。
因此它不会把"多个 Agent 说了一样的话"误写成"事实正确"，而是报告：
这些意见是否来自不同证据路径、彼此重叠多少、是否满足输出隔离条件。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from parallax.domain.models import (
    Claim,
    EvidenceUnit,
    IndependenceProfile,
    ProvenanceEdge,
    ProvenanceGraph,
    ProvenanceNode,
)


@dataclass
class DependencyAnalysis:
    components: dict[str, str]
    common_upstreams: list[str]
    unresolved: list[str]
    uncertain_readers: set[str]

    def support(self, readers: Iterable[str]) -> int:
        return len(
            {
                self.components[r]
                for r in readers
                if r in self.components and r not in self.uncertain_readers
            }
        )


def analyze_dependencies(
    assignments: Mapping[str, list[str]], evidence: Iterable[EvidenceUnit] = ()
) -> DependencyAnalysis:
    """按共同推理上游合并通道；原始文件重叠另由 Jaccard 预算处理。

    对显式血缘里的缺失节点和环保守处理。无法从未声明的隐藏调用推断独立性。
    """
    units = {unit.evidence_id: unit for unit in evidence}
    parent = {reader: reader for reader, ids in assignments.items() if ids}
    unknown: set[str] = set()
    uncertain: set[str] = set()
    artifacts: dict[str, set[str]] = defaultdict(set)
    visited: dict[str, set[str]] = defaultdict(set)

    def root(reader: str) -> str:
        while parent[reader] != reader:
            parent[reader] = parent[parent[reader]]
            reader = parent[reader]
        return reader

    def visit(eid: str, path: frozenset[str], reader: str, *, declared: bool) -> None:
        unit = units.get(eid)
        if eid in path or len(path) >= 256 or (unit is None and declared):
            unknown.add(eid)
            uncertain.add(reader)
            return
        if unit is None:
            return  # 旧调用只有 assignments，保留其可用性。
        if eid in visited[reader]:
            return
        visited[reader].add(eid)
        if unit.kind != "raw" or unit.derived_from:
            artifacts[eid].add(reader)
        for upstream in unit.derived_from:
            visit(upstream, path | {eid}, reader, declared=True)

    for reader in parent:
        for eid in assignments[reader]:
            visit(eid, frozenset(), reader, declared=bool(units))
    for readers in artifacts.values():
        ordered = sorted(readers)
        for reader in ordered[1:]:
            a, b = root(ordered[0]), root(reader)
            parent[max(a, b)] = min(a, b)
    return DependencyAnalysis(
        components={reader: root(reader) for reader in sorted(parent)},
        common_upstreams=sorted(eid for eid, readers in artifacts.items() if len(readers) > 1),
        unresolved=sorted(unknown),
        uncertain_readers=uncertain,
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
    evidence: Iterable[EvidenceUnit] = (),
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
    dependencies = analyze_dependencies(assignments, evidence)
    support = [
        dependencies.support(
            set(claim.verified_by) or by_subject[(claim.fingerprint, claim.polarity)]
        )
        for claim in claims
    ]
    claims_with_support = sum(value >= 2 for value in support)
    isolation_status = (
        "violated"
        if output_contamination
        else ("unknown" if dependencies.unresolved or not reader_count else "verified")
    )
    correlation_budget_violated = output_contamination or overlap_rate > max(
        0.0, min(1.0, max_evidence_overlap_rate)
    )
    correlation_budget_violated = (
        correlation_budget_violated
        or bool(dependencies.unresolved)
        or any(
            value < min_independent_support <= len(by_subject[(claim.fingerprint, claim.polarity)])
            for claim, value in zip(claims, support, strict=True)
        )
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
        dependency_components=dependencies.components,
        common_upstreams=dependencies.common_upstreams,
        unresolved_lineage=dependencies.unresolved,
        dependency_channel_count=dependencies.support(assignments),
    )


def build_provenance_graph(
    claims: Iterable[Claim],
    assignments: Mapping[str, list[str]],
    receipts: Iterable[object] = (),
    *,
    evidence: Iterable[EvidenceUnit] = (),
) -> ProvenanceGraph:
    claims = list(claims)
    nodes: dict[str, ProvenanceNode] = {}
    edges: set[tuple[str, str, str]] = set()

    def ensure_evidence(eid: str) -> None:
        nodes.setdefault(
            f"evidence:{eid}",
            ProvenanceNode(node_id=f"evidence:{eid}", node_type="evidence", label=eid),
        )

    for unit in evidence:
        nodes[f"evidence:{unit.evidence_id}"] = ProvenanceNode(
            node_id=f"evidence:{unit.evidence_id}",
            node_type="evidence",
            label=unit.locator,
            metadata={"kind": unit.kind, "content_hash": unit.content_hash},
        )
        for upstream in unit.derived_from:
            ensure_evidence(upstream)
            edges.add((f"evidence:{upstream}", f"evidence:{unit.evidence_id}", "derived_from"))

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
            node_id=claim_node,
            node_type="claim",
            label=claim.statement,
            metadata={
                "polarity": int(claim.polarity),
                "fingerprint": claim.fingerprint,
                "verification_status": claim.verification_status,
                "independent_support": claim.metadata.get("independent_support"),
            },
        )
        reader_node = f"reader:{claim.extracted_by}"
        nodes.setdefault(
            reader_node,
            ProvenanceNode(node_id=reader_node, node_type="reader", label=claim.extracted_by),
        )
        edges.add((reader_node, claim_node, "produced"))
        for ref in claim.source_refs:
            ensure_evidence(ref.evidence_id)
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
        kind = getattr(receipt, "kind", None)
        if kind not in {"arbitration", "coverage"}:
            continue
        receipt_id = getattr(receipt, "receipt_id", "")
        if not receipt_id:
            continue
        node_id = f"{kind}:{receipt_id}"
        payload = dict(getattr(receipt, "payload", {}) or {})
        nodes[node_id] = ProvenanceNode(
            node_id=node_id,
            node_type=kind,
            label=str(payload.get("status", "")),
            metadata=payload,
        )
        for claim_id in getattr(receipt, "claim_ids", []) or []:
            if f"claim:{claim_id}" in nodes:
                edges.add(
                    (
                        node_id,
                        f"claim:{claim_id}",
                        "arbitrated_by" if kind == "arbitration" else "covers",
                    )
                )

    return ProvenanceGraph(
        nodes=sorted(nodes.values(), key=lambda node: node.node_id),
        edges=[ProvenanceEdge(source=s, target=t, relation=r) for s, t, r in sorted(edges)],
    )
