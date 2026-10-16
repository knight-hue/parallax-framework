"""Claim 账本：结构化存储与归并。

职责边界（刻意收窄，聚合规则见 core/aggregator.py）：

    账本负责：准入校验、存储、按指纹归并、独立来源计数
    聚合器负责：状态判定、置信度计算、争议识别

分开的原因很实际——「存储」和「规则」的出错模式完全不同，混在一起没法单测，
而且换一套聚合规则时不应该动到账本。

## 交叉验证的判定用「指纹 + 极性」，不用语义相似度

指纹由插件给出确定性规则（代码审计里是 `文件:行段:缺陷类`）。语义相似度需要阈值，
阈值需要调参，调参不可复现，而且「差不多相似」在多智能体场景下会引入新的主观性。
指纹粗一点没关系（同一主体的不同表述会归一），但必须确定性。
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence

from pydantic import BaseModel, Field

from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import Claim, EvidenceUnit
from parallax.ports.claim_validator import ClaimValidator, RejectionRecord


class LedgerGroup(BaseModel):
    """同一主体指纹下的全部主张——账本的核心视图。"""

    fingerprint: str
    status: ClaimStatus = ClaimStatus.PENDING
    claim_type: str = "generic"
    claim_ids: list[str] = Field(default_factory=list)
    asserting_agents: list[str] = Field(default_factory=list)
    denying_agents: list[str] = Field(default_factory=list)
    rounds_seen: list[int] = Field(default_factory=list)

    @property
    def cross_validation_count(self) -> int:
        """独立交叉验证数 = 独立主张该主体的 Agent 个数（含最初提取者）。

        必须是**独立 Agent 去重后**的个数：同一个 Agent 跨轮重复报同一问题
        只是自证，不能算交叉验证。
        """
        return len(self.asserting_agents)

    @property
    def is_disputed(self) -> bool:
        return bool(self.asserting_agents) and bool(self.denying_agents)


class ClaimLedger:
    """Claim 账本。"""

    def __init__(self, validators: Sequence[ClaimValidator] = ()) -> None:
        self.validators = list(validators)
        self._claims: OrderedDict[str, Claim] = OrderedDict()
        self._groups: OrderedDict[str, LedgerGroup] = OrderedDict()
        self._verdicts: dict[str, ClaimStatus] = {}
        self.rejections: list[RejectionRecord] = []

    # ---- 仲裁裁决 ----

    def record_verdict(self, fingerprint: str, status: ClaimStatus) -> None:
        """落地仲裁裁决。

        裁决必须存在账本上，而不能只是改写 claim.status ——
        `Aggregator.sweep()` 每次都会按规则重算状态，
        若裁决没落地，下一次 sweep 立刻把争议又判回来，仲裁等于白做。
        """
        self._verdicts[fingerprint] = status

    def verdict_for(self, fingerprint: str) -> ClaimStatus | None:
        return self._verdicts.get(fingerprint)

    @property
    def verdicts(self) -> dict[str, ClaimStatus]:
        return dict(self._verdicts)

    # ---- 写入 ----

    def admit(self, claim: Claim, shard: list[EvidenceUnit]) -> Claim | None:
        """准入校验后入账。被拒收的 claim 会留痕，不静默丢弃。"""
        for validator in self.validators:
            result = validator.validate(claim, shard)
            if not result.ok:
                self.rejections.append(
                    RejectionRecord(
                        claim_id=claim.claim_id,
                        validator=result.validator or getattr(validator, "name", "unknown"),
                        reason=result.reason,
                        statement=claim.statement,
                    )
                )
                return None
        self._claims[claim.claim_id] = claim
        self._index(claim)
        return claim

    def add_rejection(self, record: RejectionRecord) -> None:
        self.rejections.append(record)

    # ---- 读取 ----

    @property
    def claims(self) -> list[Claim]:
        return list(self._claims.values())

    def claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def __len__(self) -> int:
        return len(self._claims)

    def groups(self) -> list[LedgerGroup]:
        """按指纹归并的账本视图。

        ⚠️ 返回的是账本**持有**的分组对象，不是每次重建的快照。
        早期版本每次调用都重建，导致 `Aggregator.sweep()` 写进分组的 status
        在下一次 `groups()` 时被抹掉——报告里所有结论都会显示成"待验证"。
        分组必须是账本状态的一部分，这个 bug 才不会再犯。
        """
        return list(self._groups.values())

    def _index(self, claim: Claim) -> None:
        """把 claim 增量并入所属分组。"""
        group = self._groups.get(claim.fingerprint)
        if group is None:
            group = LedgerGroup(fingerprint=claim.fingerprint, claim_type=claim.claim_type)
            self._groups[claim.fingerprint] = group
        group.claim_ids.append(claim.claim_id)
        if claim.round_index not in group.rounds_seen:
            group.rounds_seen.append(claim.round_index)
            group.rounds_seen.sort()
        bucket = (
            group.asserting_agents if claim.polarity == Polarity.ASSERT else group.denying_agents
        )
        if claim.extracted_by not in bucket:
            bucket.append(claim.extracted_by)
            bucket.sort()
