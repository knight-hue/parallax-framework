"""结论剥离仲裁：让仲裁者只看见观察，不看见结论。

## 为什么必须剥离结论

`Audit Without Verification`（arXiv 2609.07680）用 34.5 万次请求证明：
一个只读上游报告的问责层会退化成**转发**而不是核查——在无人提对真因的情形里，
只找回 4.1% 的真因（低于 20% 的随机猜）；把"Agent 自己给出的结论"字段删掉后，
同一批证据下的准确率升到 45.2%（+41.2pp），而对建议的顺从率从 94.4% 掉到 3.4%。

本框架的 `Claim.statement` 就是那个"结论字段"。默认仲裁器（`LLMArbitrator`）
会读到双方的自然语言结论，于是有同样的转发风险。

## 本模块的做法

`observation_view()` 把 Claim 压成 `Observation`：

- 保留：极性、缺陷类型、证据指针、引用片段、可证伪条件；
- **丢弃**：`statement`（只留哈希，供审计比对"当时它确实说了这句话"）；
- 新增 `inspect()`：仲裁者拿着指针回到原始证据上**重新推导**信号，
  而不是复述任何一方的话。

`BlindArbitrator` 因此没有任何"随大流"的自由度：它只回答
"引用位置上，证据本身是否支持该类缺陷"。

结论剥离不改变"谁有道理"，它只切断"谁说得像有道理"这条捷径。
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from parallax.core.ledger import LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import Claim, EvidenceUnit

EvidenceSignal = Literal["confirms_defect", "refutes_defect", "inconclusive"]

_LOCATOR = re.compile(r"^(?P<path>.+?):(?P<start>\d+)-(?P<end>\d+)$")

# ---- 通用信号（只描述结构性坏味道，不依赖任何特定缺陷的内部编号）----

_DEFECT_SIGNALS: dict[str, tuple[re.Pattern[str], ...]] = {
    # 把「减法结果」直接写进账本/字段，而不先判断被减数是否够减。
    "business_invariant": (
        re.compile(r"\bput\s*\([^;{}]*?-[^;{}]*?\)\s*;"),
        re.compile(r"\b\w+\s*=\s*[\w.]+\s*-\s*[\w.]+\s*;"),
    ),
    # 先写目标文件、后校验内容：写入语句出现在第一个校验分支之前。
    "atomicity": (
        re.compile(r"\bFiles\.(?:write|writeString|newOutputStream)\s*\("),
        re.compile(r"\bnew\s+(?:FileWriter|FileOutputStream)\s*\("),
    ),
    # 用整秒/整除截断算增量，却无条件把时间基准推进到当前时刻。
    "concurrency": (
        re.compile(r"/\s*1000\b"),
        re.compile(r"\blast\w*\s*=\s*now\s*;", re.IGNORECASE),
    ),
    # 吞掉异常直接返回字面量。
    "error_handling": (
        re.compile(
            r"catch\s*\([^)]*\)\s*\{(?:(?!\}[^}]*$).)*?\breturn\s+(?:0|0L|null|false|-1)\s*;", re.S
        ),
    ),
}

# 这些结构说明作者**已经**设防，信号不再成立。
_BOUNDS_GUARDS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bif\s*\([^)\n]*(?:<|>|<=|>=)\s*[\w.]"),  # 边界判断
    re.compile(r"\bMath\.(?:max|min)\s*\("),
    re.compile(r"\b(?:require|requireNonNull|checkArgument|checkState|Preconditions\.\w+)\s*\("),
)

_CONCURRENCY_GUARDS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsynchronized\s*\("),
    re.compile(r"\blast\w*\s*\+=\s*"),  # 只推进已消耗的整秒，余量得以保留
)

_ERROR_GUARDS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bthrow\s+new\s+\w+Exception"),
    re.compile(r"\b(?:log|logger|LOGGER)\.\w+\s*\("),
)

_WRITE_BEFORE_VALIDATION = re.compile(
    r"(?:Files\.(?:write|writeString|newOutputStream)|new\s+(?:FileWriter|FileOutputStream))\s*\([^;]*;"
    r"(?:(?!\bif\s*\().)*?\bif\s*\(",
    re.S,
)


class Observation(BaseModel):
    """结论剥离后的仲裁输入。

    刻意**没有** `statement` 字段：只要仲裁器能读到结论，它就会倾向于复述结论。
    需要事后审计「当时账本里确实是这句话」时，用 `statement_digest()` 对照
    `ObservationLedger.statement_digests`——摘要是不可逆的，无法拿来回放语义。
    """

    model_config = ConfigDict(frozen=True)

    claim_id: str
    fingerprint: str
    polarity: Polarity
    claim_type: str
    evidence_id: str
    locator: str
    quote: str | None = None
    trigger_conditions: tuple[str, ...] = ()
    counter_conditions: tuple[str, ...] = ()


def statement_digest(statement: str) -> str:
    """结论的不可逆摘要，只在审计里出现。"""
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()[:16]


def observation_view(claim: Claim) -> Observation:
    """把 Claim 压成不含结论文本的观察视图。"""
    ref = claim.source_refs[0]
    return Observation(
        claim_id=claim.claim_id,
        fingerprint=claim.fingerprint,
        polarity=claim.polarity,
        claim_type=claim.claim_type,
        evidence_id=ref.evidence_id,
        locator=ref.locator,
        quote=ref.quote,
        trigger_conditions=tuple(claim.trigger_conditions),
        counter_conditions=tuple(claim.counter_conditions),
    )


def observation_views(claims: Sequence[Claim]) -> list[Observation]:
    return [observation_view(claim) for claim in claims]


def _window(content: str, locator: str, *, pad: int = 2) -> str:
    """按 locator 取出证据窗口；解析失败时退回整份证据，不做静默截断。"""
    match = _LOCATOR.match(locator.strip())
    if match is None:
        return content
    start = max(1, int(match.group("start")) - pad)
    end = int(match.group("end")) + pad
    lines = content.splitlines()
    if not lines:
        return content
    return "\n".join(lines[start - 1 : min(end, len(lines))])


def inspect(claim_type: str, content: str, locator: str) -> EvidenceSignal:
    """回到证据上重新推导信号。

    返回三态而不是布尔值：`inconclusive` 是**合法且常见**的结果，
    把"没看出来"说成"没问题"才是审计层最常见的错误。
    """
    window = _window(content, locator)
    if not window.strip():
        return "inconclusive"
    checker = _CHECKERS.get(claim_type)
    if checker is None:
        return "inconclusive"
    return checker(window)


def _any(patterns: tuple[re.Pattern[str], ...], window: str) -> bool:
    return any(pattern.search(window) for pattern in patterns)


def _check_business_invariant(window: str) -> EvidenceSignal:
    if not _any(_DEFECT_SIGNALS["business_invariant"], window):
        return "inconclusive"
    return "refutes_defect" if _any(_BOUNDS_GUARDS, window) else "confirms_defect"


def _check_atomicity(window: str) -> EvidenceSignal:
    if not _any(_DEFECT_SIGNALS["atomicity"], window):
        return "inconclusive"
    if _WRITE_BEFORE_VALIDATION.search(window):
        return "confirms_defect"
    # 有写入，但校验/临时文件在写入之前：写成"证伪"是合理的有向信号。
    return "refutes_defect"


def _check_concurrency(window: str) -> EvidenceSignal:
    truncating = _any(_DEFECT_SIGNALS["concurrency"][:1], window)
    unconditional_reset = _any(_DEFECT_SIGNALS["concurrency"][1:], window)
    if not truncating:
        return "inconclusive"
    if _any(_CONCURRENCY_GUARDS, window):
        return "refutes_defect"
    return "confirms_defect" if unconditional_reset else "inconclusive"


def _check_error_handling(window: str) -> EvidenceSignal:
    if _any(_DEFECT_SIGNALS["error_handling"], window):
        return "confirms_defect"
    if re.search(r"catch\s*\(", window) and _any(_ERROR_GUARDS, window):
        return "refutes_defect"
    return "inconclusive"


_CHECKERS = {
    "business_invariant": _check_business_invariant,
    "atomicity": _check_atomicity,
    "concurrency": _check_concurrency,
    "error_handling": _check_error_handling,
}


@runtime_checkable
class EvidenceAwareArbitrator(Protocol):
    """需要原始证据才能裁决的仲裁器。

    编排图在仲裁前调用 `bind_evidence()`；不实现该协议的仲裁器（如纯 LLM 仲裁）
    行为不变。
    """

    name: str

    def bind_evidence(self, evidence: Mapping[str, EvidenceUnit]) -> None: ...

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus: ...


class BlindArbitrator:
    """结论剥离仲裁：只按证据信号投票，不看任何一方的措辞。"""

    name = "blind-evidence"

    def __init__(self) -> None:
        self._evidence: Mapping[str, EvidenceUnit] = {}

    def bind_evidence(self, evidence: Mapping[str, EvidenceUnit]) -> None:
        self._evidence = evidence

    def inspect_claim(self, claim: Claim) -> EvidenceSignal:
        ref = claim.source_refs[0]
        unit = self._evidence.get(ref.evidence_id)
        if unit is None:
            return "inconclusive"
        return inspect(claim.claim_type, unit.content, ref.locator)

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus:
        """按证据裁决，不按人数裁决。

        关键点：争议双方引用的是**同一个位置**，所以证据只可能给出一个方向。
        若按"支持哪一方的 claim 更多"计票，三人错、一人对时又变成多数赢了——
        那正是本模块要消除的从众路径。因此这里只看证据指向，不看主张数量。
        """
        confirms = 0
        refutes = 0
        inconclusive = 0
        for claim in claims:
            signal = self.inspect_claim(claim)
            claim.metadata["arbitration_input"] = "observation-only"
            claim.metadata["evidence_signal"] = signal
            if signal == "confirms_defect":
                confirms += 1
            elif signal == "refutes_defect":
                refutes += 1
            else:
                inconclusive += 1

        group_meta = {
            "arbitrator": self.name,
            "confirms": confirms,
            "refutes": refutes,
            "inconclusive": inconclusive,
        }
        for claim in claims:
            claim.metadata["arbitration"] = group_meta

        if confirms > refutes:
            return ClaimStatus.HIGH_CONFIDENCE
        if refutes > confirms:
            return ClaimStatus.PENDING
        # 证据说不出话（或自相矛盾）：保留争议。
        # "我们不确定，需要人看"比"投票选一个"更诚实——这正是 strict 模式的意义。
        return ClaimStatus.DISPUTED


class RelayArbitrator:
    """结论中继基线：只看上报结论与人数。

    这不是推荐实现，而是 2609.07680 所描述失败模式的**确定性替身**，
    用于实验对照：当仲裁层只读结论时会发生什么。
    """

    name = "relay-majority"

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus:
        assert_votes = sum(1 for claim in claims if claim.polarity == Polarity.ASSERT)
        deny_votes = len(claims) - assert_votes
        for claim in claims:
            claim.metadata["arbitration_input"] = "statement-visible"
            claim.metadata["arbitration"] = {
                "arbitrator": self.name,
                "assert_votes": assert_votes,
                "deny_votes": deny_votes,
            }
        if assert_votes > deny_votes:
            return ClaimStatus.HIGH_CONFIDENCE
        if deny_votes > assert_votes:
            return ClaimStatus.PENDING
        return ClaimStatus.DISPUTED


class StickyArbitrator:
    """结论可见但要自证的仲裁器（结论粘性可调）。

    `stickiness=1.0` 等价于 `RelayArbitrator`（完全转发结论），
    `stickiness=0.0` 等价于 `BlindArbitrator`（完全剥离）。
    中间取值用来刻画"读了结论之后还愿意去核对证据"的过渡带。

    粘性判定用 (fingerprint, stickiness) 的稳定哈希，因此同一输入永远得到同一裁决。
    """

    name = "sticky-evidence"

    def __init__(self, *, stickiness: float, seed: int = 0) -> None:
        if not 0.0 <= stickiness <= 1.0:
            raise ValueError("stickiness 必须落在 [0, 1]")
        self.stickiness = stickiness
        self.seed = seed
        self._blind = BlindArbitrator()

    def bind_evidence(self, evidence: Mapping[str, EvidenceUnit]) -> None:
        self._blind.bind_evidence(evidence)

    def _follow_conclusion(self, fingerprint: str) -> bool:
        # 只对 (seed, fingerprint) 计算一个稳定的分位点，**不含 stickiness**：
        # 这样 s 增大时"跟随结论"的集合是嵌套的，剂量—反应曲线才是单调可解释的；
        # 若把 s 也放进哈希，不同 s 会得到不同抽样，曲线会出现纯噪声的抖动。
        raw = f"{self.seed}:{fingerprint}".encode()
        rank = (int(hashlib.sha256(raw).hexdigest()[:8], 16) % 1000) / 1000.0
        return rank < self.stickiness

    async def arbitrate(self, group: LedgerGroup, claims: list[Claim]) -> ClaimStatus:
        if self._follow_conclusion(group.fingerprint):
            verdict = await RelayArbitrator().arbitrate(group, claims)
            for claim in claims:
                claim.metadata["arbitration_input"] = "statement-visible"
            return verdict
        return await self._blind.arbitrate(group, claims)


class ObservationLedger(BaseModel):
    """一次仲裁的观察快照，用于复算（"当时仲裁者能看到的全部信息"）。"""

    fingerprint: str
    observations: list[Observation] = Field(default_factory=list)
    statement_digests: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def build(cls, group: LedgerGroup, claims: Sequence[Claim]) -> ObservationLedger:
        return cls(
            fingerprint=group.fingerprint,
            observations=observation_views(claims),
            statement_digests={
                claim.claim_id: statement_digest(claim.statement) for claim in claims
            },
        )
