"""反证协议与离线参考实现。

反证器是 Claim 验证阶段的独立扩展点。它只返回可审计的三态结果，
不会把反证结果偷偷折算进多数票，也不会修改账本中的 Claim。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from parallax.domain.models import Claim, EvidenceUnit

FalsifierVerdict = Literal["confirmed", "refuted", "insufficient_evidence"]


class FalsifierResult(BaseModel):
    """一次反证尝试的结构化结果。"""

    claim_id: str
    verdict: FalsifierVerdict
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    @property
    def status(self) -> FalsifierVerdict:
        """兼容调用方使用 ``status`` 的命名。"""
        return self.verdict


@runtime_checkable
class Falsifier(Protocol):
    """Claim 反证扩展点。"""

    name: str

    def evaluate(self, claim: Claim, evidence: Sequence[EvidenceUnit]) -> FalsifierResult:
        """在给定证据上尝试确认、推翻或判定证据不足。"""
        ...


class OfflineFalsifier:
    """确定性的离线反证器。

    它用 Claim 中显式声明的触发条件和反证条件做大小写不敏感的文本匹配，
    适合单元测试、演示和没有模型凭据的流水线。匹配规则透明，不能替代
    真实执行验证，因此未匹配时返回 ``insufficient_evidence``。
    """

    name = "offline-rule-falsifier"

    def evaluate(self, claim: Claim, evidence: Sequence[EvidenceUnit]) -> FalsifierResult:
        referenced = {ref.evidence_id for ref in claim.source_refs}
        candidates = [unit for unit in evidence if unit.evidence_id in referenced]
        if not candidates:
            return FalsifierResult(
                claim_id=claim.claim_id,
                verdict="insufficient_evidence",
                reason="没有找到 Claim 引用的证据单元",
            )

        texts = {unit.evidence_id: unit.content.casefold() for unit in candidates}
        counter = [condition.casefold() for condition in claim.counter_conditions if condition]
        trigger = [condition.casefold() for condition in claim.trigger_conditions if condition]

        refuted_ids = [
            evidence_id
            for evidence_id, content in texts.items()
            if any(condition in content for condition in counter)
        ]
        if refuted_ids:
            return FalsifierResult(
                claim_id=claim.claim_id,
                verdict="refuted",
                reason="证据命中了 Claim 声明的反证条件",
                evidence_ids=sorted(refuted_ids),
            )

        confirmed_ids = [
            evidence_id
            for evidence_id, content in texts.items()
            if any(condition in content for condition in trigger)
        ]
        if confirmed_ids:
            return FalsifierResult(
                claim_id=claim.claim_id,
                verdict="confirmed",
                reason="证据命中了 Claim 声明的触发条件",
                evidence_ids=sorted(confirmed_ids),
            )

        return FalsifierResult(
            claim_id=claim.claim_id,
            verdict="insufficient_evidence",
            reason="引用证据没有命中触发条件或反证条件",
            evidence_ids=sorted(texts),
        )

    # ``falsify`` 是更直观的别名，方便接入已有调用方。
    def falsify(self, claim: Claim, evidence: Sequence[EvidenceUnit]) -> FalsifierResult:
        return self.evaluate(claim, evidence)
