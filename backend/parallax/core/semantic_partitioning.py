"""Optional bounded dependency context around each primary blind partition."""

from __future__ import annotations

from collections import deque

from parallax.core.partitioning import BlindPartitioner, Partition
from parallax.domain.models import EvidenceUnit


class SemanticClosurePartitioner(BlindPartitioner):
    def __init__(self, *args, closure_hops: int = 1, max_context_units: int = 8, **kwargs):
        super().__init__(*args, **kwargs)
        self.closure_hops = closure_hops
        self.max_context_units = max_context_units

    def partition(
        self, units: list[EvidenceUnit], round_index: int, focus_groups: list[str] | None = None
    ) -> list[Partition]:
        partitions = super().partition(units, round_index, focus_groups)
        by_id = {unit.evidence_id: unit for unit in units}
        result = []
        for partition in partitions:
            selected = {unit.evidence_id for unit in partition.units}
            primary_count = len(selected)
            queue = deque((eid, 0) for eid in sorted(selected))
            while queue:
                eid, depth = queue.popleft()
                if depth >= self.closure_hops:
                    continue
                for dependency in by_id[eid].metadata.get("risk_dependencies", []):
                    if dependency in by_id and dependency not in selected:
                        if len(selected) - primary_count >= self.max_context_units:
                            continue
                        selected.add(dependency)
                        queue.append((dependency, depth + 1))
            result.append(
                Partition(
                    reader_id=partition.reader_id,
                    round_index=round_index,
                    units=tuple(by_id[eid] for eid in sorted(selected)),
                )
            )
        return result
