"""扩展点 3：claim 校验器（可选，可串联多个）。

职责只有一个：**在 claim 入账本之前否决它**。
典型用途是「漂移检测」——claim 声称的内容跟它引用的原始证据对不上，
说明提取阶段已经跑偏，这种 claim 不该污染账本。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from parallax.domain.models import Claim, EvidenceUnit


class ValidationResult(BaseModel):
    """校验结论。"""

    ok: bool
    reason: str = ""
    validator: str = ""

    @classmethod
    def accept(cls, validator: str = "") -> ValidationResult:
        return cls(ok=True, validator=validator)

    @classmethod
    def reject(cls, reason: str, validator: str = "") -> ValidationResult:
        return cls(ok=False, reason=reason, validator=validator)


@runtime_checkable
class ClaimValidator(Protocol):
    """claim 准入校验协议。"""

    name: str

    def validate(self, claim: Claim, shard: list[EvidenceUnit]) -> ValidationResult:
        """返回 ok=False 时，该 claim 被拒收并记入 run manifest 的拒收清单。"""
        ...


class RejectionRecord(BaseModel):
    """被拒收的 claim 留痕——拒收也要可审计，不能静默丢弃。"""

    claim_id: str
    validator: str
    reason: str
    statement: str = ""
