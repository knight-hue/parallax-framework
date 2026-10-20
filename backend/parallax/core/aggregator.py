"""聚合器：把账本里的主张按**规则**判定成高置信 / 待验证 / 争议。

## 为什么「规则化」本身是抗从众设计

如果用 LLM 做聚合（让 Writer 读所有 claim 后「综合判断」），那聚合层就成了新的
从众入口：Writer 会倾向于采纳出现次数最多的说法、忽略孤立的异见。
把判定写成确定性规则，聚合器就**没有自由裁量权，也就没有随大流的机会**。

规则写死、可单测、可逐条解释——这是对「聚合层不从众」的工程化承诺。

## 置信度：对数几率累加（weight of evidence）

    confidence = sigmoid( Σ_assert logit(r_i) − Σ_deny logit(r_j) )

r 为 Agent 声誉（Beta 后验均值）。这样：
- 声誉 0.5 的 Agent 贡献 0 权重（既不加分也不减分，符合「无信息」直觉）
- 声誉高的 Agent 交叉验证才显著推高置信度
- 反方 Agent 按同一规则**做减法**，异见有对称话语权

## 「异见者不受惩罚」

多数场景会用「少数服从多数」更新 Agent 声誉——但这本身是一种从众压力：
Agent 会学会「不要第一个说不同意见」。因此本实现规定：
处于争议、尚未仲裁的少数方**不做任何声誉扣减**（见 core/reputation.py）。
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from parallax.core.ledger import ClaimLedger, LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import Claim

_LOGIT_R_FLOOR = 0.05
_LOGIT_R_CEIL = 0.95


def _logit(reliability: float) -> float:
    """把声誉(概率)转成证据权重(对数几率)。夹逼避免除零与极端值。"""
    r = min(max(reliability, _LOGIT_R_FLOOR), _LOGIT_R_CEIL)
    return math.log(r / (1 - r))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


class AggregationRules(BaseModel):
    """聚合规则参数。全部显式，无隐藏魔法数字。"""

    support_threshold: int = 2
    """多少个独立 Agent 报出同一主体才算高置信。"""

    def validate_rules(self) -> None:
        if self.support_threshold < 1:
            raise ValueError("support_threshold 至少为 1")


class Aggregator:
    """规则化聚合器。"""

    def __init__(self, ledger: ClaimLedger, rules: AggregationRules | None = None) -> None:
        self.ledger = ledger
        self.rules = rules or AggregationRules()
        self.rules.validate_rules()

    def sweep(self) -> list[LedgerGroup]:
        """重算全部结论并回填到 claim 上。幂等，每轮补检后调用一次。"""
        groups = self.ledger.groups()
        for group in groups:
            group.status = self.decide_status(group)
            confidence = self.confidence(group)
            disputed_peers: dict[str, list[str]] = self._dispute_map(group)
            for claim_id in group.claim_ids:
                claim = self.ledger.claim(claim_id)
                if claim is None:  # pragma: no cover - 防御性
                    continue
                claim.status = group.status
                claim.verified_by = list(
                    group.asserting_agents
                    if claim.polarity == Polarity.ASSERT
                    else group.denying_agents
                )
                claim.disputed_with = disputed_peers.get(claim_id, [])
                claim.confidence = confidence
        return groups

    def decide_status(self, group: LedgerGroup) -> ClaimStatus:
        """规则优先级：仲裁裁决 > 争议 > 交叉验证达标 > 孤证。"""
        verdict = self.ledger.verdict_for(group.fingerprint)
        if verdict is not None:
            return verdict
        if group.is_disputed:
            return ClaimStatus.DISPUTED
        if group.cross_validation_count >= self.rules.support_threshold:
            return ClaimStatus.HIGH_CONFIDENCE
        return ClaimStatus.PENDING

    def confidence(self, group: LedgerGroup) -> float:
        """见模块 docstring。

        ⚠️ 按 Agent 去重，每个 Agent 只投一次票。
        否则一个 Agent 每轮重复报同一问题就会不断抬高置信度——那是自证，不是交叉验证。
        """
        signed_weight: dict[str, float] = {}
        for claim_id in group.claim_ids:
            claim = self.ledger.claim(claim_id)
            if claim is None or claim.extracted_by in signed_weight:
                continue
            sign = 1.0 if claim.polarity == Polarity.ASSERT else -1.0
            signed_weight[claim.extracted_by] = sign * _logit(claim.reputation_at_extraction)
        return round(_sigmoid(sum(signed_weight.values())), 4)

    def arbitration_queue(self, groups: list[LedgerGroup] | None = None) -> list[LedgerGroup]:
        """需要第三方仲裁的争议组。

        仲裁者应当**盲读**：只看争议双方的 claim 与源证据，不看声誉排名，
        否则仲裁本身就变成了「谁的声誉高谁赢」。
        """
        groups = groups if groups is not None else self.ledger.groups()
        return [g for g in groups if g.status == ClaimStatus.DISPUTED]

    def apply_arbitration(self, group: LedgerGroup, upheld: ClaimStatus) -> None:
        """把仲裁裁决写回账本与该组的 claim，使其退出 DISPUTED 状态。"""
        self.ledger.record_verdict(group.fingerprint, upheld)
        for claim_id in group.claim_ids:
            claim = self.ledger.claim(claim_id)
            if claim is not None:
                claim.status = upheld
        group.status = upheld

    def _dispute_map(self, group: LedgerGroup) -> dict[str, list[str]]:
        """claim_id -> 与之立场相反的 claim_id 列表。"""
        if not group.is_disputed:
            return {}
        by_polarity: dict[Polarity, list[str]] = {Polarity.ASSERT: [], Polarity.DENY: []}
        for claim_id in group.claim_ids:
            claim: Claim | None = self.ledger.claim(claim_id)
            if claim is not None:
                by_polarity[claim.polarity].append(claim_id)
        out: dict[str, list[str]] = {}
        for claim_id in by_polarity[Polarity.ASSERT]:
            out[claim_id] = sorted(by_polarity[Polarity.DENY])
        for claim_id in by_polarity[Polarity.DENY]:
            out[claim_id] = sorted(by_polarity[Polarity.ASSERT])
        return out
