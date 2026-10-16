"""声誉：存储与更新策略。

## 「异见者不受惩罚」——本项目最反直觉、也最重要的一条规则

直觉做法是用「少数服从多数」更新 Agent 声誉：跟多数一致就加分，唱反调就扣分。
**但这本身就是一种从众压力**——Agent 会迅速学会「不要第一个说不同意见」，
于是我们在框架内部亲手重建了我们想消灭的那件事。

因此本实现规定：

    交叉验证通过        → 所有主张者 +1 verified
    孤证 (PENDING)      → 不更新（既未被验证也未被否证，不携带信息）
    争议 (DISPUTED)     → **不更新，双方都不动**（等仲裁，不预先惩罚少数方）
    仲裁裁决后          → 胜方 arbitration_win，败方 arbitration_loss

声誉分用 Beta 后验均值：score = (1 + 命中) / (2 + 命中 + 未命中)
新 Agent 从 0.5 中性起步，样本少时不会暴涨，无需调参，可解释。
"""

from __future__ import annotations

from collections import OrderedDict

from parallax.core.ledger import ClaimLedger, LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import AgentReputation


class InMemoryReputationStore:
    """内存实现，用于开发与测试。

    生产替换为 Redis/Postgres 实现即可——`ReputationStore` 协议已经定死了三个方法，
    上层不感知具体存储。
    """

    def __init__(self) -> None:
        self._reps: OrderedDict[str, AgentReputation] = OrderedDict()

    def get(self, agent_id: str, role: str = "reader") -> AgentReputation:
        rep = self._reps.get(agent_id)
        if rep is None:
            rep = AgentReputation(agent_id=agent_id, role=role)
            self._reps[agent_id] = rep
        return rep

    def save(self, reputation: AgentReputation) -> None:
        self._reps[reputation.agent_id] = reputation

    def all(self) -> list[AgentReputation]:
        return list(self._reps.values())

    def scores(self) -> dict[str, float]:
        """给评测用的快照：agent_id -> 声誉分。"""
        return {r.agent_id: round(r.score(), 4) for r in self._reps.values()}


class ReputationPolicy:
    """把聚合结论转成声誉变动。"""

    def __init__(self, store: InMemoryReputationStore) -> None:
        self.store = store

    def apply_cross_validation(
        self,
        groups: list[LedgerGroup],
        ledger: ClaimLedger,
        run_id: str,
    ) -> dict[str, float]:
        """按高置信结论给主张者记 verified。

        返回本次变动的 agent -> 分数，便于实验报告展示。
        """
        updated: dict[str, float] = {}
        for group in groups:
            if group.status != ClaimStatus.HIGH_CONFIDENCE:
                # PENDING / DISPUTED 都不更新，理由见模块 docstring
                continue
            for claim_id in group.claim_ids:
                claim = ledger.claim(claim_id)
                if claim is None:
                    continue
                rep = self.store.get(claim.extracted_by)
                rep.record(run_id=run_id, claim_id=claim_id, outcome="verified")
                self.store.save(rep)
                updated[claim.extracted_by] = round(rep.score(), 4)
        return updated

    def apply_arbitration(
        self,
        group: LedgerGroup,
        ledger: ClaimLedger,
        run_id: str,
        upheld: ClaimStatus,
    ) -> dict[str, float]:
        """仲裁裁决落地后才结算声誉。

        裁决为 HIGH_CONFIDENCE → ASSERT 方胜；裁决为 PENDING → 视为未能证实，
        DENY 方胜（「无法证实」不等于「证伪」，所以只做 win/loss 记录，不改 claim 结论语义）。
        """
        winners_polarity = (
            Polarity.ASSERT if upheld == ClaimStatus.HIGH_CONFIDENCE else Polarity.DENY
        )
        updated: dict[str, float] = {}
        for claim_id in group.claim_ids:
            claim = ledger.claim(claim_id)
            if claim is None:
                continue
            outcome = (
                "arbitration_win" if claim.polarity == winners_polarity else "arbitration_loss"
            )
            rep = self.store.get(claim.extracted_by)
            rep.record(run_id=run_id, claim_id=claim_id, outcome=outcome)
            self.store.save(rep)
            updated[claim.extracted_by] = round(rep.score(), 4)
        return updated
