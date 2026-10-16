"""评测指标：全部为纯函数，可单独单测。

## 指标定义

**M1 召回率** = 命中的植入缺陷数 / 植入缺陷总数
    主指标，对应评审要的「隐蔽缺陷检出率」。

**M2 冗余率** = 1 − 不同指纹数 / claim 总数
    对应市场公认第一痛点「重复发现 / 噪音」。注意冗余不完全是坏事
    （交叉验证依赖它），所以必须与 M1 一起看，不能单独优化。

**M3 有效独立通道数 K\\*** = (tr G)² / tr(G²)，其中 Gᵢⱼ = |Fᵢ ∩ Fⱼ|
    Fᵢ 是第 i 个 Agent 报出的指纹集合。这是重叠矩阵特征值的**参与率**：

        所有 Agent 完全一致  → G 秩为 1 → K* = 1（等于只有一条通道）
        所有 Agent 完全互斥  → G 为对角阵 → K* = N（N 条独立通道）

    它直接量化了 arXiv 2602.03794 的「有效独立通道数」——而且**不需要 ground truth**。

**M4 覆盖率** = 报告里覆盖率矩阵的填充率，衡量补检闭环是否把该看的都看了。

**M5 精确率** = 归入某条植入缺陷的 claim 数 / claim 总数
    衡量「报出来的东西有多少是真的」，对应痛点「误报 / 假阳性」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from parallax.domain.models import Claim, Report

_LOCATOR_RE = re.compile(r"^(?P<file>.+):(?P<start>\d+)-(?P<end>\d+)$")


@dataclass(frozen=True)
class ClaimLocation:
    file: str
    start: int | None
    end: int | None


def parse_location(claim: Claim) -> ClaimLocation | None:
    """从 claim 的源指针里取出文件与行区间。

    行号优先取插件写入的 metadata（精确），否则从 locator 解析；
    两者都拿不到时只返回文件名——匹配退化为「同文件」。
    """
    if not claim.source_refs:
        return None
    ref = claim.source_refs[0]
    start = claim.metadata.get("line_start")
    end = claim.metadata.get("line_end")
    if isinstance(start, int) and isinstance(end, int):
        return ClaimLocation(_normalise(ref.locator.split(":")[0]), start, end)

    match = _LOCATOR_RE.match(ref.locator)
    if match:
        return ClaimLocation(
            _normalise(match.group("file")), int(match.group("start")), int(match.group("end"))
        )
    return ClaimLocation(_normalise(ref.locator), None, None)


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _gap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """两个闭区间的距离；重叠则为 0。"""
    if a_end < b_start:
        return b_start - a_end
    if b_end < a_start:
        return a_start - b_end
    return 0


class MatchedClaim(BaseModel):
    claim_id: str
    agent: str
    fingerprint: str
    defect_id: str | None = None
    distance: int | None = None
    verdict: str = "unmatched"  # hit | duplicate | unmatched


class DefectOutcome(BaseModel):
    defect_id: str
    title: str
    defect_class: str
    file: str
    found_by: list[str] = Field(default_factory=list)

    @property
    def hit(self) -> bool:
        return bool(self.found_by)


class MatchReport(BaseModel):
    matches: list[MatchedClaim] = Field(default_factory=list)
    defects: list[DefectOutcome] = Field(default_factory=list)

    @property
    def hits(self) -> int:
        return sum(1 for d in self.defects if d.hit)

    @property
    def total_defects(self) -> int:
        return len(self.defects)

    @property
    def matched_claims(self) -> int:
        return sum(1 for m in self.matches if m.verdict in {"hit", "duplicate"})

    @property
    def duplicates(self) -> int:
        return sum(1 for m in self.matches if m.verdict == "duplicate")


def match_claims(claims: list[Claim], defects, line_tolerance: int = 25) -> MatchReport:
    """把 claim 归到植入缺陷上。

    匹配**以位置为主、类目为辅**：真正要问的是「找到没有」，
    而不是「类目标签是否与出题人一致」——拿类目做硬门槛会低估检出能力。

    贪心分配按距离升序全局进行，避免「先到先得」把近距离的 claim 浪费掉。
    同一个植入缺陷的其余 claim 记为 duplicate —— 它们是冗余，不是错误。
    """
    outcomes = [
        DefectOutcome(
            defect_id=d.id,
            title=d.title,
            defect_class=d.defect_class,
            file=_normalise(d.file),
        )
        for d in defects
    ]
    by_id = {d.id: d for d in defects}

    matches: list[MatchedClaim] = []
    assigned: dict[str, str] = {}

    candidates: list[tuple[int, str, int, Claim]] = []
    for index, claim in enumerate(claims):
        location = parse_location(claim)
        if location is None:
            matches.append(_unmatched(claim))
            continue
        for outcome in outcomes:
            if location.file != outcome.file:
                continue
            defect = by_id[outcome.defect_id]
            if location.start is None or location.end is None:
                distance = 0
            else:
                distance = _gap(location.start, location.end, defect.line_start, defect.line_end)
            if distance <= line_tolerance:
                candidates.append((distance, outcome.defect_id, index, claim))

    candidates.sort(key=lambda item: (item[0], item[2]))
    verdict_by_index: dict[int, str] = {}
    for _distance, defect_id, index, _claim in candidates:
        if index in verdict_by_index:
            continue
        if defect_id in assigned:
            verdict_by_index[index] = f"dup:{defect_id}"
            continue
        assigned[defect_id] = str(index)
        verdict_by_index[index] = defect_id

    for index, claim in enumerate(claims):
        verdict = verdict_by_index.get(index)
        if verdict is None:
            matches.append(_unmatched(claim))
            continue
        if verdict.startswith("dup:"):
            defect_id = verdict[4:]
            defect = by_id[defect_id]
            matches.append(
                MatchedClaim(
                    claim_id=claim.claim_id,
                    agent=claim.extracted_by,
                    fingerprint=claim.fingerprint,
                    defect_id=defect_id,
                    distance=_distance_to(claim, defect),
                    verdict="duplicate",
                )
            )
            # 冗余 claim 同样要计入「谁发现了它」。
            # 漏掉这一步会系统性低估交叉验证数，让「孤证数」虚高——
            # 而孤证数正是衡量从众的核心指标，错在这里整个结论都会失真。
            outcome = next(o for o in outcomes if o.defect_id == defect_id)
            if claim.extracted_by not in outcome.found_by:
                outcome.found_by.append(claim.extracted_by)
            continue
        defect = by_id[verdict]
        matches.append(
            MatchedClaim(
                claim_id=claim.claim_id,
                agent=claim.extracted_by,
                fingerprint=claim.fingerprint,
                defect_id=verdict,
                distance=_distance_to(claim, defect),
                verdict="hit",
            )
        )
        outcome = next(o for o in outcomes if o.defect_id == verdict)
        if claim.extracted_by not in outcome.found_by:
            outcome.found_by.append(claim.extracted_by)

    for outcome in outcomes:
        outcome.found_by.sort()
    return MatchReport(matches=matches, defects=outcomes)


def _unmatched(claim: Claim) -> MatchedClaim:
    return MatchedClaim(
        claim_id=claim.claim_id,
        agent=claim.extracted_by,
        fingerprint=claim.fingerprint,
        verdict="unmatched",
    )


def _distance_to(claim: Claim, defect) -> int | None:
    location = parse_location(claim)
    if location is None or location.start is None or location.end is None:
        return None
    return _gap(location.start, location.end, defect.line_start, defect.line_end)


def effective_channels(agent_fingerprints: dict[str, set[str]]) -> float:
    """K\\*：有效独立通道数。

    用重叠矩阵（Gram 矩阵）特征值的**参与率**来定义：

        Gᵢⱼ = |Fᵢ ∩ Fⱼ|        （Fᵢ 为第 i 个 Agent 报出的指纹集合）
        K*  = (tr G)² / tr(G²)  =  (Σᵢ|Fᵢ|)² / Σᵢ Σⱼ |Fᵢ ∩ Fⱼ|²

    ⚠️ 分母是交集的**平方和**。少了这个平方，完全互斥时会得到"发现总数"
    而不是"通道数"（第一版就是这么错的，K* 算出 13 而 Agent 只有 9 个）。

    两个端点行为：
        所有 Agent 完全一致 → G 秩为 1 → K* = 1（等于只有一条通道）
        所有 Agent 完全互斥 → G 为对角阵 → K* = N（N 条独立通道）

    它直接量化了 arXiv 2602.03794 的「有效独立通道数」，
    且**不需要 ground truth**，因此也能在没有标注的真实仓库上直接测。
    """
    sets = [s for s in agent_fingerprints.values() if s]
    n = len(sets)
    if n <= 1:
        return float(n)

    total = sum(len(s) for s in sets)
    if total == 0:
        return 0.0

    trace = total  # tr(G) = Σᵢ|Fᵢ|
    trace_sq = 0  # tr(G²) = Σᵢ Σⱼ |Fᵢ∩Fⱼ|²
    for a in sets:
        for b in sets:
            inter = len(a & b)
            trace_sq += inter * inter

    if trace_sq == 0:
        return float(n)
    return round((trace * trace) / trace_sq, 4)


class ArmMetrics(BaseModel):
    """一个实验组在一个任务上的全部指标。"""

    arm: str
    task_id: str
    reader_count: int = 0
    recall: float | None = None
    """召回率。**None 表示无 ground truth**——真实仓库没有标注，这个值算不出来。

    早先这里默认 0.0，那会把"没标注"和"一个都没找到"混成同一个数字，
    是最容易自欺的一类指标错误（0% 召回看起来像机制失效，其实只是没标尺）。
    """
    precision: float | None = None
    """精确率。同样在无标注时为 None：没有 ground truth 时"命中"无从判定。"""
    redundancy: float = 0.0
    effective_channels: float = 0.0
    """K\\*：有效独立通道数。值域 [1, agent_count]。

    ⚠️ **必须与 `agent_count` 一起读**。多轮运行的每一轮都会生成全新 Reader 身份
    （见 `BlindPartitioner.reader_ids`），所以 3 轮 × 6 Reader 的臂实际有 18 个不同 Agent，
    它的 K\\* 上限是 18 而不是 6。直接拿"1 轮 6 Agent"与"3 轮 18 Agent"的 K\\* 比大小
    **不是同口径比较**——这个坑在真实仓库验证阶段才发现，此前的文档确实踩了它。
    """
    agent_count: int = 0
    """实际产出过 claim 的不同 Agent 数（多轮下 = 每轮读者数之和）。K\\* 的上限。"""

    @property
    def channels_ratio(self) -> float:
        """归一化独立通道占比 = K\\* / agent_count，值域 (0, 1]。

        跨臂比较应当用这个而不是裸 K\\*：它回答的是
        「这 N 个 Agent 发挥出了几成独立性」，
        从而让轮次不同、读者数不同的两个臂可比。
        """
        if not self.agent_count:
            return 0.0
        return round(self.effective_channels / self.agent_count, 4)

    coverage_fill_rate: float = 0.0
    rounds: int = 0
    total_claims: int = 0
    distinct_fingerprints: int | None = None
    """去重后的主体指纹数。**None 表示旧产物未记录该字段**（早于本字段加入）。

    ⚠️ 与 `duplicates` **不是同一个东西**，早先的汇总把它们都印成"冗余"，
    在无标注的真实仓库上会同时显示「冗余率 63%」和「冗余 0」，自相矛盾。
    - `distinct_fingerprints`：不同指纹数 → `redundancy = 1 - distinct/total`
    - `duplicates`：**多条 claim 命中同一个植入缺陷**的条数，只在有 ground truth 时有意义

    不从 `redundancy` 反推：那个值只保留 4 位小数，反推出来的整数可能差 1，
    把估计值当实测值印出来正是这个项目一直在修的那类错误。
    """
    hits: int = 0
    planted: int = 0
    duplicates: int = 0
    """命中同一植入缺陷的重复 claim 数（需要 ground truth；无标注时恒为 0）。"""
    unmatched: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    schema_retries: int = 0
    readers_failed: int = 0
    """执行失败的 Reader 数。

    必须与「漏检」分开统计：Reader 挂了会拉低召回，
    若混在一起就会把工程故障误读成机制缺陷。
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stop_reason: str = ""
    defects: list[DefectOutcome] = Field(default_factory=list)
    """逐缺陷命中情况——从众最直接的证据：哪些缺陷只被 1 个 Agent 看到。"""

    @property
    def sole_source_defects(self) -> int:
        """只被 1 个 Agent 发现的缺陷数。"""
        return sum(1 for d in self.defects if len(d.found_by) == 1)

    @property
    def unanimous_defects(self) -> int:
        """被所有 Agent 都发现的缺陷数。"""
        return sum(
            1 for d in self.defects if self.reader_count and len(d.found_by) >= self.reader_count
        )

    def missed_ids(self) -> list[str]:
        return [d.defect_id for d in self.defects if not d.hit]


def compute_metrics(
    *,
    arm: str,
    task_id: str,
    report: Report,
    claims: list[Claim],
    defects,
    usage: dict[str, int],
    reader_count: int,
    readers_failed: int = 0,
) -> ArmMetrics:
    match = match_claims(claims, defects)

    total_claims = len(claims)
    distinct_fingerprints = len({c.fingerprint for c in claims})

    per_agent: dict[str, set[str]] = {}
    for claim in claims:
        per_agent.setdefault(claim.extracted_by, set()).add(claim.fingerprint)

    # 只统计"产出过 claim"的 Agent：空跑的 Reader 不构成通道，
    # 把它们算进分母会把占比无端拉低。
    agent_count = len([s for s in per_agent.values() if s])

    return ArmMetrics(
        arm=arm,
        task_id=task_id,
        reader_count=reader_count,
        # 无标注时留 None 而不是 0.0：0% 召回会被误读成"机制失效"，
        # 而真相是"没有标尺可量"。
        recall=round(match.hits / match.total_defects, 4) if match.total_defects else None,
        precision=(
            round(match.matched_claims / total_claims, 4)
            if match.total_defects and total_claims
            else None
        ),
        redundancy=round(1.0 - distinct_fingerprints / total_claims, 4) if total_claims else 0.0,
        effective_channels=effective_channels(per_agent),
        agent_count=agent_count,
        coverage_fill_rate=round(report.coverage.fill_rate(), 4),
        rounds=len(report.manifest.rounds),
        total_claims=total_claims,
        distinct_fingerprints=distinct_fingerprints,
        hits=match.hits,
        planted=match.total_defects,
        duplicates=match.duplicates,
        unmatched=sum(1 for m in match.matches if m.verdict == "unmatched"),
        llm_calls=usage.get("calls", 0),
        llm_failures=usage.get("failures", 0),
        schema_retries=usage.get("schema_retries", 0),
        readers_failed=readers_failed,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        stop_reason=report.manifest.stop_reason.value if report.manifest.stop_reason else "",
        defects=match.defects,
    )
