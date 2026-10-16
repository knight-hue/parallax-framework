"""领域枚举。"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class ClaimStatus(StrEnum):
    """claim 的聚合结论。

    判定完全由规则给出（见 core/aggregator.py），不做主观打分：

        DISPUTED         存在极性相反的主张（有 Agent 说「有问题」，也有说「没问题」）
        HIGH_CONFIDENCE  被 >= support_threshold 个独立 Agent 交叉验证
        PENDING          只有单一来源（孤证），待验证
    """

    DISPUTED = "disputed"
    HIGH_CONFIDENCE = "high_confidence"
    PENDING = "pending"


class Polarity(IntEnum):
    """claim 的主张方向。

    这是争议检测的关键：两条 claim 若主体指纹相同、极性相反，
    即构成「互相矛盾」，必须触发仲裁而不是简单多数表决。
    """

    ASSERT = 1
    DENY = -1


class RoundStopReason(StrEnum):
    """补检循环的停止原因，写进 run manifest 供审计。"""

    COVERAGE_SATISFIED = "coverage_satisfied"
    MAX_ROUNDS_REACHED = "max_rounds_reached"
    NO_NEW_EVIDENCE = "no_new_evidence"
    BUDGET_EXHAUSTED = "budget_exhausted"
