"""确定性的自适应补检调度。

调度器只决定下一轮优先看哪些维度，不读取任何 Reader 的自然语言输出，
因此不会破坏盲读隔离。排序使用可解释的缺口分数，并以维度名稳定打破平局。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class AdaptiveFocusScheduler:
    """按证据缺口、争议和未确认 Claim 选择补检重点。"""

    def rank(
        self,
        rows: Sequence[str],
        *,
        uncovered_rows: Sequence[str] = (),
        dispute_rows: Sequence[str] = (),
        unconfirmed_rows: Sequence[str] = (),
        evidence_support: Mapping[str, int] | None = None,
    ) -> list[str]:
        uncovered = set(uncovered_rows)
        disputed = set(dispute_rows)
        unconfirmed = set(unconfirmed_rows)
        support = evidence_support or {}

        def score(row: str) -> tuple[int, int, str]:
            # 硬缺口优先，其次争议，再其次孤证；支持越少越优先。
            priority = (4 if row in uncovered else 0) + (2 if row in disputed else 0)
            priority += 1 if row in unconfirmed else 0
            return (-priority, support.get(row, 0), row)

        return sorted(set(rows), key=score)
