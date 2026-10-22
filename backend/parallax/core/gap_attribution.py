"""覆盖缺口归因：把"没覆盖到"拆成"没派人读"与"派了人但没读到"。

## 为什么必须区分

覆盖率监控只知道"这一格是空的"，但空格有两种完全不同的成因：

    分区缺口（partition_gap）  证据压根没被足够多独立 Reader 看过 —— 系统层的漏派
    漏检（reader_miss）        够了 min_support 个 Reader 都读了，没人报出 —— 读者层的漏报

处置完全不同：前者要增加派发，后者要换人/换分区/提高冗余，甚至只能交还人工。
把它们混成一个"未覆盖"数字，补检就只是在瞎加轮次。

## 怎么估漏检率

同一份证据被 k 个独立盲读 Reader 看过，每个 Reader 报出一组 claim 指纹。
把每对 Reader 看成两次独立捕获，用 Chapman 估计量：

    N̂ = (n₁ + 1)(n₂ + 1) / (m + 1) − 1        m = 两人共同报出的指纹数

`m = 0` 时估计量发散（无重捕），此时**不给数字**——硬凑一个无穷大或"漏检 100%"
都是伪造精度。多人场景取两两估计的中位数，抗单对异常。

估计出的 p̄ = 观测到的独立指纹数 / N̂ 就是"单个 Reader 的检出概率"。
对某一份证据，r 个 Reader 全都漏掉的概率是 (1 − p̄)^r。

**这只是估计，不是证明**：Chapman 假设各 Reader 独立同分布、总体封闭。
真实模型同源、证据难易不均，都会让假设偏离。因此报告里必须同时给出
重捕对数、估计区间与"无法估计"的情形。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Literal

from parallax.domain.models import Claim

GapKind = Literal["partition_gap", "reader_miss", "healthy", "unresolved"]

_P_CEIL = 0.95
"""单 Reader 检出率的上限。

有限样本永远无法证明 p=1；若不加限制，运行级估计恰好覆盖全部已观测指纹时会得到
p=1，于是 (1-p)^r = 0，把“零检出”当成“必然漏检”。留一个保守上限，
宁可高估漏检概率，也不输出“绝对不会漏”的伪确定性。
"""


def chapman(n1: int, n2: int, recaptured: int) -> float | None:
    """Chapman 估计量。无重捕时返回 None：不发散、不硬凑。"""
    if n1 <= 0 or n2 <= 0 or recaptured <= 0:
        return None
    return (n1 + 1) * (n2 + 1) / (recaptured + 1) - 1


@dataclass(frozen=True)
class CaptureEstimate:
    """一次捕获—重捕估计的结果。"""

    observed: int
    estimated_total: float | None
    detection_probability: float | None
    recapture_pairs: int
    method: str
    pair_estimates: tuple[float, ...] = ()

    @property
    def estimable(self) -> bool:
        return self.estimated_total is not None and self.detection_probability is not None

    @property
    def miss_rate(self) -> float | None:
        if not self.estimable or not self.observed:
            return None
        return round(max(0.0, 1.0 - self.observed / self.estimated_total), 6)


def estimate_capture(
    reader_claims: Mapping[str, Iterable[str]],
    *,
    method: str = "chapman-median",
) -> CaptureEstimate:
    """对"Reader → 报出的指纹集合"做捕获—重捕估计。

    只对**至少报出一条**的 Reader 配对：零检出的 Reader 说明这次采样没抽到，
    把它的 0 代入 Chapman 会系统性地把总体估小。
    """
    detected = {reader: set(claims) for reader, claims in reader_claims.items() if claims}
    observed = len({fingerprint for claims in detected.values() for fingerprint in claims})
    if len(detected) < 2:
        return CaptureEstimate(
            observed=observed,
            estimated_total=None,
            detection_probability=None,
            recapture_pairs=0,
            method=method,
        )

    estimates: list[float] = []
    for left, right in combinations(sorted(detected), 2):
        shared = len(detected[left] & detected[right])
        value = chapman(len(detected[left]), len(detected[right]), shared)
        if value is not None:
            estimates.append(value)

    if not estimates:
        return CaptureEstimate(
            observed=observed,
            estimated_total=None,
            detection_probability=None,
            recapture_pairs=0,
            method=method,
        )

    ordered = sorted(estimates)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    total = max(float(observed), median)
    return CaptureEstimate(
        observed=observed,
        estimated_total=round(total, 4),
        detection_probability=round(min(_P_CEIL, observed / total), 6) if total else None,
        recapture_pairs=len(estimates),
        method=method,
        pair_estimates=tuple(round(value, 4) for value in estimates),
    )


@dataclass(frozen=True)
class GapAttribution:
    """单条证据的缺口归因。"""

    evidence_id: str
    group: str
    readers: int
    claims: int
    kind: GapKind
    reason: str
    missing_probability: float | None = None
    """r 个 Reader 全部漏掉的概率 (1-p̄)^r；无估计时为 None。"""

    @property
    def needs_more_readers(self) -> bool:
        return self.kind == "partition_gap"


@dataclass(frozen=True)
class AttributionReport:
    """一次运行的全部缺口归因。"""

    min_support: int
    run_estimate: CaptureEstimate
    items: tuple[GapAttribution, ...] = ()
    by_kind: dict[str, int] = field(default_factory=dict)

    @property
    def reader_miss_count(self) -> int:
        return self.by_kind.get("reader_miss", 0)

    @property
    def partition_gap_count(self) -> int:
        return self.by_kind.get("partition_gap", 0)

    @property
    def actionable_groups(self) -> list[str]:
        """需要下一轮定向补检的分组（两类缺口都要，但含义不同）。"""
        groups: list[str] = []
        for item in self.items:
            if item.kind in {"partition_gap", "reader_miss"} and item.group not in groups:
                groups.append(item.group)
        return groups


def attribute_gaps(
    *,
    assignments: Mapping[str, Sequence[str]],
    claims: Sequence[Claim],
    groups: Mapping[str, str],
    min_support: int,
    miss_threshold: float = 0.5,
) -> AttributionReport:
    """逐条证据判定缺口成因，并用运行级估计给出"集体漏检"概率。

    Args:
        assignments: reader_id -> 该 Reader 读过的 evidence_id 列表（跨轮累积）。
        claims: 账本里的全部 claim。
        groups: evidence_id -> 审视维度（用于聚焦补检）。
        min_support: 一条证据至少要几个独立 Reader 看过。
        miss_threshold: 全员漏检概率低于该值时，把"零检出"判为 reader_miss。
    """
    readers_by_evidence: dict[str, list[str]] = defaultdict(list)
    for reader, evidence_ids in assignments.items():
        for evidence_id in evidence_ids:
            readers_by_evidence[evidence_id].append(reader)

    claims_by_evidence: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for claim in claims:
        for ref in claim.source_refs:
            claims_by_evidence[ref.evidence_id][claim.extracted_by].add(claim.fingerprint)

    pooled: dict[str, set[str]] = defaultdict(set)
    for by_reader in claims_by_evidence.values():
        for reader, fingerprints in by_reader.items():
            pooled[reader] |= fingerprints
    run_estimate = estimate_capture(pooled)

    items: list[GapAttribution] = []
    for evidence_id in sorted(readers_by_evidence):
        readers = sorted(set(readers_by_evidence[evidence_id]))
        by_reader = claims_by_evidence.get(evidence_id, {})
        observed = len({fp for fingerprints in by_reader.values() for fp in fingerprints})
        group = groups.get(evidence_id, evidence_id)

        if len(readers) < min_support:
            items.append(
                GapAttribution(
                    evidence_id=evidence_id,
                    group=group,
                    readers=len(readers),
                    claims=observed,
                    kind="partition_gap",
                    reason=(
                        f"只有 {len(readers)} 个独立 Reader 看过，未达 min_support={min_support}；"
                        "属于系统层漏派，不是读者漏报"
                    ),
                )
            )
            continue

        if observed:
            items.append(
                GapAttribution(
                    evidence_id=evidence_id,
                    group=group,
                    readers=len(readers),
                    claims=observed,
                    kind="healthy",
                    reason=f"{len(readers)} 个 Reader 共产出 {observed} 条独立 claim",
                )
            )
            continue

        probability = None
        if run_estimate.detection_probability is not None:
            probability = round((1 - run_estimate.detection_probability) ** len(readers), 6)
        if probability is not None and probability < miss_threshold:
            items.append(
                GapAttribution(
                    evidence_id=evidence_id,
                    group=group,
                    readers=len(readers),
                    claims=0,
                    kind="reader_miss",
                    reason=(
                        f"{len(readers)} 个 Reader 均未报出；按运行级检出率 "
                        f"p̄={run_estimate.detection_probability:.2f}，全员漏检概率仅 {probability:.1%}。"
                        "这是漏检候选而不是缺陷结论：下一步是定向补检；"
                        "零检出同样可能是证据真的干净，本层只给出待验证假设。"
                    ),
                    missing_probability=probability,
                )
            )
            continue

        items.append(
            GapAttribution(
                evidence_id=evidence_id,
                group=group,
                readers=len(readers),
                claims=0,
                kind="unresolved",
                reason=(
                    "零检出且运行级估计不足以判断是干净还是集体漏检"
                    if probability is None
                    else f"零检出，但全员漏检概率仍有 {probability:.1%}，无法排除漏检"
                ),
                missing_probability=probability,
            )
        )

    by_kind: dict[str, int] = defaultdict(int)
    for item in items:
        by_kind[item.kind] += 1
    return AttributionReport(
        min_support=min_support,
        run_estimate=run_estimate,
        items=tuple(items),
        by_kind=dict(sorted(by_kind.items())),
    )
