"""可选的争议仲裁器。

## 为什么仲裁是「可选扩展点」而不是核心三接口之一

核心三接口（EvidenceAdapter / ReaderPlugin / ClaimValidator）是**每个场景都必须实现**的。
仲裁器不是：没有它，框架依然是完整可用的——争议组会被原样保留为 DISPUTED，
既不被多数票淹没，也不被静默丢弃。这本身就是可以交付的结论
（「我们不确定，需要人看」比「我们投票选了一个」更诚实）。

默认注入 `NullArbitrator`（什么都不做）。需要自动收敛时再注入 LLMArbitrator。

## 仲裁者必须盲读

仲裁器**不得**知道双方 Agent 的声誉排名——否则仲裁就退化成
「谁的声誉高谁赢」，那又是一次从众。
`Claim.reputation_at_extraction` 字段保留在 claim 上供审计，
但实现仲裁器时应显式忽略它。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from parallax.core.ledger import LedgerGroup
from parallax.domain.enums import ClaimStatus
from parallax.domain.models import Claim


@runtime_checkable
class Arbitrator(Protocol):
    """争议仲裁协议。"""

    name: str

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus:
        """给出裁决。

        Returns:
            HIGH_CONFIDENCE  证实「问题存在/结论成立」一侧
            PENDING          无法证实（注意：**这不等于证伪**）
        """
        ...


class NullArbitrator:
    """默认仲裁器：不做任何裁决，争议保持 DISPUTED。"""

    name = "null"

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus:
        return ClaimStatus.DISPUTED
