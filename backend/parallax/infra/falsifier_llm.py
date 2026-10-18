"""基于 OpenAI-compatible 客户端的独立反证器。

反证调用使用独立提示词，只提供 Claim 的来源证据、触发条件和反证条件。
它不会把多数票、Reader 声誉或聚合状态传给模型，避免把反证退化成再次投票。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import BaseModel, Field

from parallax.domain.models import Claim, EvidenceUnit
from parallax.ports.falsifier import FalsifierResult
from parallax.ports.llm import ChatMessage, LLMClient

logger = logging.getLogger(__name__)


class _ModelVerdict(BaseModel):
    verdict: str = Field(description="confirmed、refuted 或 insufficient_evidence")
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


_SYSTEM = """你是一个独立的代码审查反证者。

只依据用户给出的证据判断 Claim：
- confirmed：证据支持 Claim，且没有出现反证条件；
- refuted：证据明确满足反证条件，或明确否定 Claim；
- insufficient_evidence：证据不足，不能确认或推翻。

不要根据多数票、Reader 数量、声誉或 Claim 的聚合状态判断。
只能从给出的 evidence_ids 中选择证据，并只输出 JSON。"""


class LLMFalsifier:
    """可选的真实模型反证器；失败时保守返回证据不足。"""

    name = "llm-falsifier"

    def __init__(self, client: LLMClient, *, max_evidence_chars: int = 24000) -> None:
        self.client = client
        self.max_evidence_chars = max(1000, max_evidence_chars)

    async def aevaluate(self, claim: Claim, evidence: Sequence[EvidenceUnit]) -> FalsifierResult:
        referenced = {ref.evidence_id for ref in claim.source_refs}
        candidates = [unit for unit in evidence if unit.evidence_id in referenced]
        if not candidates:
            return FalsifierResult(
                claim_id=claim.claim_id,
                verdict="insufficient_evidence",
                reason="没有找到 Claim 引用的证据单元",
            )

        evidence_text: list[str] = []
        used_chars = 0
        for unit in candidates:
            remaining = self.max_evidence_chars - used_chars
            if remaining <= 0:
                break
            excerpt = unit.content[:remaining]
            evidence_text.append(f"[{unit.evidence_id}] {unit.locator}\n{excerpt}")
            used_chars += len(excerpt)

        user = (
            f"Claim ID: {claim.claim_id}\n"
            f"Claim: {claim.statement}\n"
            f"Trigger conditions: {claim.trigger_conditions or ['(none)']}\n"
            f"Counter conditions: {claim.counter_conditions or ['(none)']}\n\n"
            "Evidence:\n" + "\n\n".join(evidence_text)
        )
        try:
            verdict = await self.client.complete_json(
                [
                    ChatMessage(role="system", content=_SYSTEM),
                    ChatMessage(role="user", content=user),
                ],
                _ModelVerdict,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001 - 验证失败必须保守落盘
            logger.warning("模型反证失败，Claim %s 保持证据不足：%s", claim.claim_id, exc)
            return FalsifierResult(
                claim_id=claim.claim_id,
                verdict="insufficient_evidence",
                reason=f"反证模型调用失败：{type(exc).__name__}",
            )

        allowed = {"confirmed", "refuted", "insufficient_evidence"}
        result_verdict = verdict.verdict if verdict.verdict in allowed else "insufficient_evidence"
        allowed_ids = {unit.evidence_id for unit in candidates}
        evidence_ids = sorted({item for item in verdict.evidence_ids if item in allowed_ids})
        reason = verdict.reason
        if result_verdict == "insufficient_evidence" and verdict.verdict not in allowed:
            reason = f"模型返回了未知 verdict：{verdict.verdict}"
        return FalsifierResult(
            claim_id=claim.claim_id,
            verdict=result_verdict,  # type: ignore[arg-type]
            reason=reason,
            evidence_ids=evidence_ids,
        )
