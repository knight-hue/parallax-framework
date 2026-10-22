"""独立性准入闸门：把"独立性指标"变成"是否放行结论"的控制。

## 为什么指标必须变成闸门

`core/independence.py` 已经能算出有效独立通道数、归一化独立性、证据重叠率，
但此前这些数字只写进画像和回执——**没有任何行为依赖它们**。
这意味着"独立性不足"只是一个好看的报表，系统照样把结论标成高置信。

文献里普遍止步于"我们度量了独立性"（InfoDelphi 等）。本模块把它推进一步：

    度量 → 重分区（提高冗余）→ 仍不达标 → 降级为待验证 + 标记运行

## 三种模式

    off      不参与控制（保留旧行为，便于对照）
    observe  只报告"本应如何处置"，不改写结论（默认，安全）
    enforce  真正改写：先尝试重分区，用尽尝试次数后降级

## 为什么输出污染不能被"重分区"修复

Reader 看到了别人的结论，说明**隔离已经破了**。再派一轮新 Reader 不能撤销
已经发生的污染——所以这种情况直接降级，不浪费一轮预算。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from parallax.domain.enums import ClaimStatus
from parallax.domain.models import IndependenceProfile

GateMode = Literal["off", "observe", "enforce"]
GateAction = Literal["accept", "observe", "repartition", "downgrade"]
GateRemedy = Literal["reduce_redundancy", "add_reader", "none"]

MAX_GATE_READERS = 6
"""闸门为了提高独立性最多加到几个 Reader。"""


def suggest_remedy(
    profile: IndependenceProfile | None,
    *,
    overlap_budget: float,
    n_readers: int,
    redundancy: int,
    max_readers: int = MAX_GATE_READERS,
) -> tuple[GateRemedy, str]:
    """决定“怎么提高独立性”。

    方向很容易搞反：本框架的 redundancy 是**用独立性换交叉验证**的旋钮
    （冗余越高，Reader 之间的证据重叠越多，有效独立通道越少）。所以：

        证据重叠已超预算  → 降 redundancy（恢复独立性，代价是交叉验证变少）
        重叠不高但通道仍少 → 加 Reader（多开独立通道，不牺牲现有交叉验证）

    两个方向都不能再动时返回 none，由下一轮聚合去降级，而不是无效空转。
    """
    if (
        profile is not None
        and profile.evidence_overlap_rate > max(0.0, min(1.0, overlap_budget))
        and redundancy > 1
    ):
        return (
            "reduce_redundancy",
            f"证据重叠 {profile.evidence_overlap_rate:.2f} 超过预算 {overlap_budget:.2f}，"
            f"冗余 {redundancy} → {redundancy - 1}",
        )
    if n_readers < max_readers:
        return "add_reader", f"独立通道不足，Reader {n_readers} → {n_readers + 1}"
    return "none", "冗余已到底且 Reader 已到上限，无法再提高独立性"


@dataclass(frozen=True)
class GateDecision:
    """一次准入判定。"""

    action: GateAction
    reason: str
    attempts: int
    effective_channels: float
    normalized_independence: float

    @property
    def blocking(self) -> bool:
        """是否需要改写结论（重分区不直接改写，但会再花一轮预算）。"""
        return self.action in {"repartition", "downgrade"}


class IndependenceGate:
    """独立性准入闸门。"""

    def __init__(
        self,
        *,
        mode: GateMode = "observe",
        min_effective_channels: float = 0.0,
        min_normalized_independence: float = 0.0,
        max_attempts: int = 1,
    ) -> None:
        if mode not in {"off", "observe", "enforce"}:
            raise ValueError(f"未知的闸门模式：{mode}")
        if min_effective_channels < 0 or not 0.0 <= min_normalized_independence <= 1.0:
            raise ValueError("独立性阈值必须非负，归一化阈值落在 [0, 1]")
        if max_attempts < 0:
            raise ValueError("max_attempts 不能为负")
        self.mode = mode
        self.min_effective_channels = min_effective_channels
        self.min_normalized_independence = min_normalized_independence
        self.max_attempts = max_attempts

    def evaluate(self, profile: IndependenceProfile, *, attempts: int) -> GateDecision:
        effective = float(profile.effective_channel_count)
        normalized = float(profile.normalized_independence)
        base = {
            "attempts": attempts,
            "effective_channels": effective,
            "normalized_independence": normalized,
        }

        if self.mode == "off":
            return GateDecision(action="accept", reason="闸门关闭，指标只做记录", **base)

        if profile.isolation_status == "violated":
            reason = "输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染"
            return GateDecision(
                action="observe" if self.mode == "observe" else "downgrade",
                reason=reason,
                **base,
            )

        below_effective = effective < self.min_effective_channels
        below_normalized = normalized < self.min_normalized_independence
        if not (below_effective or below_normalized):
            return GateDecision(
                action="accept",
                reason=(
                    f"独立性达标：有效通道 {effective:.2f} ≥ {self.min_effective_channels:.2f}，"
                    f"归一化 {normalized:.2%} ≥ {self.min_normalized_independence:.2%}"
                ),
                **base,
            )

        gap = []
        if below_effective:
            gap.append(f"有效通道 {effective:.2f} < {self.min_effective_channels:.2f}")
        if below_normalized:
            gap.append(f"归一化独立性 {normalized:.2%} < {self.min_normalized_independence:.2%}")
        detail = "；".join(gap)

        if self.mode == "observe":
            return GateDecision(
                action="observe",
                reason=f"独立性不足（{detail}）。observe 模式只报告，不改写结论",
                **base,
            )

        if attempts < self.max_attempts:
            return GateDecision(
                action="repartition",
                reason=f"独立性不足（{detail}）：提高冗余重分区后重跑（第 {attempts + 1} 次尝试）",
                **base,
            )
        return GateDecision(
            action="downgrade",
            reason=f"独立性不足（{detail}）且重分区尝试已用尽：结论降级为待验证",
            **base,
        )


def blocked_fingerprints(groups) -> set[str]:
    """本轮需要阻断（不得进入高置信）的指纹集。"""
    return {group.fingerprint for group in groups if group.status == ClaimStatus.HIGH_CONFIDENCE}
