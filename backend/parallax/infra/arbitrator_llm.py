"""基于模型的通用仲裁器（场景无关）。

拿到争议双方的主张与各自引用的证据摘录，让模型只依据证据判断哪一侧被支持。
提示词刻意做成场景无关——不引入第四个插件接口，也对得起「通用框架」的定位。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from parallax.core.ledger import LedgerGroup
from parallax.domain.enums import ClaimStatus
from parallax.domain.models import Claim
from parallax.ports.llm import ChatMessage, LLMClient

logger = logging.getLogger(__name__)


class ArbitrationVerdict(BaseModel):
    supported_side: str = Field(description="'assert' 或 'deny' 或 'unclear'")
    rationale: str = Field(default="", description="一句话理由")


_SYSTEM = """你是一个中立的争议仲裁者。

你会看到同一条主张的两个对立版本，以及双方各自引用的证据摘录。
你的任务：**只依据给出的证据摘录**判断哪一侧被支持。

规则：
- 不要考虑哪一方说得更多或更自信，只看证据本身是否支持该主张。
- 如果证据不足以支持任何一侧，回答 "unclear"——不确定是允许且被期待的答案。
- 不要引入任何未在证据摘录中出现的信息。

只输出 JSON：{"supported_side": "assert|deny|unclear", "rationale": "..."}"""

_ARB_SCHEMA = ArbitrationVerdict


class LLMArbitrator:
    """用模型做仲裁。

    `redact_statements=True` 时**不把双方的自然语言结论交给模型**，只给立场、
    证据指针与引用片段。这是对 `Audit Without Verification`（arXiv 2609.07680）的直接应用：
    删掉「结论字段」能让审计层从「转发」回到「核查」。
    """

    name = "llm"

    def __init__(self, client: LLMClient, *, redact_statements: bool = False) -> None:
        self.client = client
        self.redact_statements = redact_statements
        self.name = "llm-redacted" if redact_statements else "llm"

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus:
        payload = "\n\n".join(
            self._render(claim, redact=self.redact_statements)
            for claim in claims
            if claim is not None
        )
        messages = [
            ChatMessage(role="system", content=_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"争议主体指纹：{group.fingerprint}\n\n双方主张与证据：\n{payload}\n\n请裁决。"
                ),
            ),
        ]
        try:
            verdict = await self.client.complete_json(messages, _ARB_SCHEMA, temperature=0.0)
        except Exception as exc:  # noqa: BLE001 - 仲裁失败不应让整轮崩掉
            logger.warning("仲裁调用失败，争议保持未决：%s", exc)
            return ClaimStatus.DISPUTED

        side = getattr(verdict, "supported_side", "unclear")
        # 注意：unclear → PENDING（「无法证实」），而不是 DISPUTED。
        # 这个区别是重要的：它表示"已审查但证据不足"，而不是"还没解决"。
        if side == "assert":
            return ClaimStatus.HIGH_CONFIDENCE
        if side == "deny":
            return ClaimStatus.PENDING
        return ClaimStatus.PENDING

    @staticmethod
    def _render(claim: Claim, *, redact: bool = False) -> str:
        stance = "主张问题存在" if claim.polarity == 1 else "主张问题不存在"
        refs = "\n".join(
            f"  - [{ref.adapter}] {ref.locator}"
            + (f"\n    摘录：{ref.quote[:300]}" if ref.quote else "")
            for ref in claim.source_refs
        )
        head = f"[{claim.extracted_by}] {stance}"
        if not redact:
            head += f"：{claim.statement}"
        return f"{head}\n  证据：\n{refs}"
