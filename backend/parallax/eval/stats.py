"""配对统计：把已落的 metrics.json 变成带区间与显著性判定的结论。

## 为什么需要这一层

`variance.pairwise_verdict` 用的是「最小逐次差 > 两组标准差之和」的启发式，
它自己的措辞就是「n 下不能排除偶然」——那是描述统计，不是推断。
评审问的下一句必然是"这个差有多大把握不是噪声"，所以必须有区间和检验。

## 三条硬约束（不遵守就得出假结论）

1. **配对靠 defect_id，不靠汇总召回率。**
   同一个植入缺陷在对照组/实验组各是一次 是/否，这才是可配对单位。
   拿两条臂的总召回率做两比例检验会把"题目难易"混进"机制差异"。

2. **不做插补。** 没有 ground truth 的任务（真实仓库）不参与检出率检验；
   失败臂（`valid=false`、Reader 失败、errors 非空）整条剔除，而不是当 0 分。
   `variance.collect` 已经是这个口径，这里保持一致。

3. **重复实验不合并计数。** 同一批缺陷跑 3 次仍是同一批缺陷，
   把 (缺陷, 重复) 当独立样本会让 p 值虚低。所以本模块按单次运行给结论，
   重复之间只比较"方向是否一致"，稳定性交给 `variance.render_variance`。

## 实现的检验

- **McNemar 精确检验**：只看不一致对（实验组独中 / 对照组独中），
  双侧精确二项分布，不依赖大样本近似。
- **配对自助法区间**：对缺陷做有放回重采样，给风险差（召回率之差）的置信区间。
- **符号翻转置换检验**：给连续指标（K\\*、token 等）的配对差做分布无关检验。
- **Holm 校正**：同时看多个缺陷类/多个指标时控制族错误率。
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 精确枚举符号翻转的上限。2^16 = 65536 次组合，毫秒级；再大改用蒙特卡洛。
EXACT_SIGN_FLIP_LIMIT = 16


# ---------------------------------------------------------------- 基础检验


def mcnemar_exact(treatment_win: int, treatment_loss: int) -> float:
    """McNemar 精确检验（双侧）。

    `treatment_win`：实验组找到了、对照组没找到的缺陷数
    `treatment_loss`：对照组找到了、实验组没找到的缺陷数

    只由不一致对决定，一致对（两边都中/都不中）不提供信息。
    """
    if treatment_win < 0 or treatment_loss < 0:
        raise ValueError("不一致对计数不能为负")
    discordant = treatment_win + treatment_loss
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(treatment_win, treatment_loss) + 1))
    return min(1.0, 2.0 * tail / 2**discordant)


def sign_flip_p(diffs: list[float], *, resamples: int = 20000, seed: int = 20261028) -> float:
    """配对符号翻转检验（双侧）。

    零假设是"处理对每条样本没有方向性影响"。n 小时枚举全部 2^n 种符号组合，
    否则用固定种子的蒙特卡洛——固定种子是为了任何人都能复算出同一个 p。
    """
    nonzero = [d for d in diffs if d != 0]
    if not nonzero:
        return 1.0
    observed = abs(sum(nonzero))
    n = len(nonzero)
    if n <= EXACT_SIGN_FLIP_LIMIT:
        extreme = 0
        for mask in range(1 << n):
            total = 0.0
            for index, value in enumerate(nonzero):
                total += value if mask >> index & 1 else -value
            if abs(total) >= observed - 1e-12:
                extreme += 1
        return extreme / (1 << n)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(resamples):
        total = sum(value if rng.random() < 0.5 else -value for value in nonzero)
        if abs(total) >= observed - 1e-12:
            extreme += 1
    return (extreme + 1) / (resamples + 1)


def bootstrap_mean_ci(
    values: list[float],
    *,
    resamples: int = 20000,
    seed: int = 20261028,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """均值的百分位自助法区间。空样本返回 (0, 0)，由调用方负责标注 n。"""
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    low = means[int(math.floor((alpha / 2) * resamples))]
    high = means[min(resamples - 1, int(math.ceil((1 - alpha / 2) * resamples)) - 1)]
    return (low, high)


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm 逐步下降校正，返回同键的校正后 p。"""
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    total = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, value) in enumerate(ordered):
        candidate = min(1.0, (total - rank) * value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


# ---------------------------------------------------------------- 数据装配


@dataclass(frozen=True)
class PairedDefects:
    """一个任务上、两条臂之间按 defect_id 配对后的四格表。"""

    task_id: str
    both: int
    only_control: int
    only_treatment: int
    neither: int
    unpaired: int = 0

    @property
    def planted(self) -> int:
        return self.both + self.only_control + self.only_treatment + self.neither

    @property
    def control_hits(self) -> int:
        return self.both + self.only_control

    @property
    def treatment_hits(self) -> int:
        return self.both + self.only_treatment

    @property
    def control_recall(self) -> float:
        return self.control_hits / self.planted if self.planted else 0.0

    @property
    def treatment_recall(self) -> float:
        return self.treatment_hits / self.planted if self.planted else 0.0

    @property
    def risk_difference(self) -> float:
        return self.treatment_recall - self.control_recall

    def units(self) -> list[tuple[bool, bool]]:
        """展开到逐缺陷的 (对照组命中, 实验组命中)，供自助法重采样用。"""
        return (
            [(True, True)] * self.both
            + [(True, False)] * self.only_control
            + [(False, True)] * self.only_treatment
            + [(False, False)] * self.neither
        )


@dataclass
class ArmSummary:
    """一条臂在一次运行上的描述统计（只统计有 GT 且有效的任务）。"""

    arm: str
    tasks: int = 0
    planted: int = 0
    hits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    sole_source_defects: int = 0
    unanimous_defects: int = 0
    threshold_sources: list[str] = field(default_factory=list)
    effective_channels: list[float] = field(default_factory=list)
    redundancies: list[int] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.hits / self.planted if self.planted else 0.0

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def tokens_per_hit(self) -> float | None:
        """每次真阳性的 token 成本。

        命中为 0、或产物没记录用量（旧运行全为 0）时返回 None——
        把它们当成 0 成本是最容易骗过自己的那类指标错误。
        """
        if not self.tokens or not self.hits:
            return None
        return self.tokens / self.hits

    @property
    def calls_per_hit(self) -> float | None:
        """每次真阳性的调用次数。早期产物只记了 calls，没记 token，这个量仍可算。"""
        if not self.llm_calls or not self.hits:
            return None
        return self.llm_calls / self.hits

    @property
    def sole_source_rate(self) -> float:
        return self.sole_source_defects / self.hits if self.hits else 0.0


@dataclass
class Comparison:
    control: str
    treatment: str
    control_summary: ArmSummary
    treatment_summary: ArmSummary
    pairs: list[PairedDefects]
    mcnemar_p: float = 1.0
    risk_difference: float = 0.0
    risk_difference_ci: tuple[float, float] = (0.0, 0.0)
    alpha: float = 0.05

    # 汇总四格表
    @property
    def both(self) -> int:
        return sum(p.both for p in self.pairs)

    @property
    def only_control(self) -> int:
        return sum(p.only_control for p in self.pairs)

    @property
    def only_treatment(self) -> int:
        return sum(p.only_treatment for p in self.pairs)

    @property
    def neither(self) -> int:
        return sum(p.neither for p in self.pairs)

    @property
    def planted(self) -> int:
        return sum(p.planted for p in self.pairs)

    @property
    def significant(self) -> bool:
        return self.mcnemar_p < self.alpha

    def direction(self) -> str:
        if self.only_treatment > self.only_control:
            return "实验组更好"
        if self.only_control > self.only_treatment:
            return "实验组更差"
        return "无差别"


def load_metrics_file(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "arms" not in payload:
        raise ValueError(f"{path} 不是 metrics.json（缺少 arms 字段）")
    return payload


def _usable(entry: dict[str, Any]) -> bool:
    if entry.get("errors"):
        return False
    if entry.get("valid") is False:
        return False
    return not entry.get("readers_failed")


def arm_entries(doc: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """{臂名: {task_id: 条目}}，只保留可用条目。"""
    table: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in doc.get("arms", []):
        if not _usable(entry):
            continue
        arm = entry.get("arm")
        task_id = entry.get("task_id")
        if not arm or not task_id:
            continue
        table.setdefault(arm, {})[task_id] = entry
    return table


def summarise(entries: dict[str, dict[str, Any]], arm: str) -> ArmSummary:
    summary = ArmSummary(arm=arm, tasks=len(entries))
    for entry in entries.values():
        summary.planted += int(entry.get("planted") or 0)
        summary.hits += int(entry.get("hits") or 0)
        summary.prompt_tokens += int(entry.get("prompt_tokens") or 0)
        summary.completion_tokens += int(entry.get("completion_tokens") or 0)
        summary.llm_calls += int(entry.get("llm_calls") or 0)
        summary.effective_channels.append(float(entry.get("effective_channels") or 0.0))
        config = entry.get("config") or {}
        if isinstance(config.get("redundancy"), int):
            summary.redundancies.append(config["redundancy"])
        # 「全员一致」的阈值必须是**实际产出过 claim 的 Agent 数**：
        # 多轮臂每一轮都会生成全新 Reader 身份，用 reader_count 会把阈值算低、多算一致。
        threshold = int(entry.get("agent_count") or entry.get("reader_count") or 0)
        summary.threshold_sources.append(
            "agent" if entry.get("agent_count") else ("reader" if threshold else "missing")
        )
        for defect in entry.get("defects") or []:
            found = len(defect.get("found_by") or [])
            if found == 1:
                summary.sole_source_defects += 1
            if threshold and found >= threshold:
                summary.unanimous_defects += 1
    return summary


def pair_task(
    control_entry: dict[str, Any], treatment_entry: dict[str, Any], task_id: str
) -> PairedDefects | None:
    """按 defect_id 配对同一任务的逐缺陷命中情况；无共同缺陷集合时返回 None。"""
    control = {d["defect_id"]: bool(d.get("found_by")) for d in control_entry.get("defects") or []}
    treatment = {
        d["defect_id"]: bool(d.get("found_by")) for d in treatment_entry.get("defects") or []
    }
    shared = sorted(set(control) & set(treatment))
    if not shared:
        return None
    unpaired = len(set(control) ^ set(treatment))
    both = only_control = only_treatment = neither = 0
    for defect_id in shared:
        in_control, in_treatment = control[defect_id], treatment[defect_id]
        if in_control and in_treatment:
            both += 1
        elif in_control:
            only_control += 1
        elif in_treatment:
            only_treatment += 1
        else:
            neither += 1
    return PairedDefects(
        task_id=task_id,
        both=both,
        only_control=only_control,
        only_treatment=only_treatment,
        neither=neither,
        unpaired=unpaired,
    )


def compare(
    doc: dict[str, Any],
    control: str,
    treatment: str,
    *,
    resamples: int = 20000,
    seed: int = 20261028,
    alpha: float = 0.05,
) -> Comparison | None:
    """在一次运行上比较两条臂。任一侧缺失或全部任务无 GT 时返回 None。"""
    table = arm_entries(doc)
    if control not in table or treatment not in table:
        return None
    pairs: list[PairedDefects] = []
    for task_id, control_entry in table[control].items():
        treatment_entry = table[treatment].get(task_id)
        if treatment_entry is None:
            continue
        paired = pair_task(control_entry, treatment_entry, task_id)
        if paired is not None and paired.planted:
            pairs.append(paired)
    if not pairs:
        return None

    comparison = Comparison(
        control=control,
        treatment=treatment,
        control_summary=summarise(table[control], control),
        treatment_summary=summarise(table[treatment], treatment),
        pairs=pairs,
        alpha=alpha,
    )
    comparison.mcnemar_p = mcnemar_exact(comparison.only_treatment, comparison.only_control)
    units = [unit for pair in pairs for unit in pair.units()]
    per_defect = [float(t) - float(c) for c, t in units]
    comparison.risk_difference = sum(per_defect) / len(per_defect)
    comparison.risk_difference_ci = bootstrap_mean_ci(
        per_defect, resamples=resamples, seed=seed, alpha=alpha
    )
    return comparison


# ---------------------------------------------------------------- 渲染


def _percent(value: float) -> str:
    return f"{value:.1%}"


def render_comparison(comparison: Comparison, *, label: str = "") -> str:
    """单次运行的双臂对照表。"""
    cs, ts = comparison.control_summary, comparison.treatment_summary
    low, high = comparison.risk_difference_ci
    lines = [
        f"### {label or comparison.control + ' vs ' + comparison.treatment}",
        "",
        "| 臂 | 任务 | 植入 | 命中 | 召回 | 调用 | 调用/命中 | token/命中 | 独有发现 | 全员一致 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in (cs, ts):
        per_hit = "—" if summary.tokens_per_hit is None else f"{summary.tokens_per_hit:,.0f}"
        per_call = "—" if summary.calls_per_hit is None else f"{summary.calls_per_hit:.1f}"
        lines.append(
            f"| `{summary.arm}` | {summary.tasks} | {summary.planted} | {summary.hits} "
            f"| {_percent(summary.recall)} | {summary.llm_calls} | {per_call} | {per_hit} "
            f"| {summary.sole_source_defects} | {summary.unanimous_defects} |"
        )
    lines += [
        "",
        f"- 配对缺陷：实验组独中 **{comparison.only_treatment}**，对照组独中 "
        f"**{comparison.only_control}**，两边都中 {comparison.both}，两边都漏 "
        f"{comparison.neither}（n={comparison.planted}）",
        f"- 独有发现占比：实验组 {ts.sole_source_defects} 个（{ts.sole_source_rate:.0%} "
        f"of 命中），对照组 {cs.sole_source_defects} 个（{cs.sole_source_rate:.0%}）",
        f"- 风险差（实验组 − 对照组）：**{comparison.risk_difference:+.1%}**"
        f"，95% 自助法区间 [{low:+.1%}, {high:+.1%}]",
        f"- McNemar 精确检验 p = **{comparison.mcnemar_p:.4g}**"
        f"（α={comparison.alpha}，{'显著' if comparison.significant else '不显著'}）",
        f"- 方向：{comparison.direction()}"
        + ("；区间跨 0，不能排除无差异" if low <= 0 <= high else "；区间不跨 0，方向与噪声已拉开"),
    ]
    unpaired = sum(pair.unpaired for pair in comparison.pairs)
    if unpaired:
        lines.append(f"- ⚠️ 有 {unpaired} 个缺陷只在一边出现，已排除在配对之外")
    if len(comparison.pairs) == 1:
        lines.append(
            "- ⚠️ 只覆盖 1 个任务：同一任务内的缺陷共享同一批 Reader 与同一个仓库，"
            "独立性有限，这里的 p 值应视为**乐观下界**"
        )
    control_redundancy = set(cs.redundancies)
    treatment_redundancy = set(ts.redundancies)
    if control_redundancy and treatment_redundancy:
        if control_redundancy != treatment_redundancy:
            lines.append(
                "- ⚠️ 两臂冗余不同（`"
                + ",".join(str(v) for v in sorted(control_redundancy))
                + "` vs `"
                + ",".join(str(v) for v in sorted(treatment_redundancy))
                + "`）：「独有发现」受分区影响，跨冗余比较该列无效；"
                "召回与配对检验不受影响"
            )
    else:
        lines.append(
            "- ⚠️ 产物未记录冗余配置（早期运行），无法核实两臂分区是否相同："
            "「独有发现」列请勿跨臂比较"
        )
    if "reader" in cs.threshold_sources or "reader" in ts.threshold_sources:
        lines.append(
            "- ⚠️ 该运行未记录 `agent_count`，「全员一致」退回 `reader_count` 判定，"
            "多轮臂下会多算一致"
        )
    if "missing" in cs.threshold_sources or "missing" in ts.threshold_sources:
        lines.append("- ⚠️ 该运行既无 `agent_count` 也无 `reader_count`，「全员一致」恒为 0")
    return "\n".join(lines)


def render_report(
    comparisons: list[tuple[str, Comparison]], *, alpha: float = 0.05, source: str = ""
) -> str:
    """多份运行的汇总报告；同时给出 Holm 校正后的显著性。"""
    lines = [
        "# 配对统计报告",
        "",
        f"来源：`{source}`" if source else "来源：未标注",
        "",
        "> 口径：按 `defect_id` 配对；无 GT 的任务与失败臂不参与；"
        "重复实验不合并计数（同一批缺陷重复跑不是独立样本）。",
        "",
    ]
    for label, comparison in comparisons:
        lines.append(render_comparison(comparison, label=label))
        lines.append("")
    if len(comparisons) > 1:
        adjusted = holm({label: c.mcnemar_p for label, c in comparisons})
        lines += [
            "## Holm 校正后的 p（同一份报告内多次比较）",
            "",
            "| 运行 | 原始 p | 校正 p |",
            "| --- | ---: | ---: |",
        ]
        for label, comparison in comparisons:
            lines.append(f"| {label} | {comparison.mcnemar_p:.4g} | {adjusted[label]:.4g} |")
        lines.append("")
    return "\n".join(lines)


def collect_comparisons(
    paths: list[Path],
    control: str,
    treatment: str,
    *,
    resamples: int = 20000,
    seed: int = 20261028,
    alpha: float = 0.05,
) -> tuple[list[tuple[str, Comparison]], list[str]]:
    """从一批 metrics.json 里收集可比对照；返回 (对照列表, 跳过说明)。"""
    found: list[tuple[str, Comparison]] = []
    skipped: list[str] = []
    for path in paths:
        doc = load_metrics_file(path)
        comparison = compare(doc, control, treatment, resamples=resamples, seed=seed, alpha=alpha)
        label = path.parent.name if path.name == "metrics.json" else path.stem
        if comparison is None:
            skipped.append(f"{path}（缺少 `{control}`/`{treatment}` 或无 GT 任务）")
            continue
        found.append((label, comparison))
    return found, skipped


def _round(value: float, digits: int = 6) -> float:
    return round(value, digits)


def comparison_payload(comparison: Comparison) -> dict[str, Any]:
    return {
        "control": comparison.control,
        "treatment": comparison.treatment,
        "planted": comparison.planted,
        "both": comparison.both,
        "only_control": comparison.only_control,
        "only_treatment": comparison.only_treatment,
        "neither": comparison.neither,
        "risk_difference": _round(comparison.risk_difference),
        "risk_difference_ci": [_round(v) for v in comparison.risk_difference_ci],
        "mcnemar_p": _round(comparison.mcnemar_p),
        "significant": comparison.significant,
        "control_recall": _round(comparison.control_summary.recall),
        "treatment_recall": _round(comparison.treatment_summary.recall),
        "control_tokens_per_hit": comparison.control_summary.tokens_per_hit,
        "treatment_tokens_per_hit": comparison.treatment_summary.tokens_per_hit,
        "per_task": [
            {
                "task_id": pair.task_id,
                "planted": pair.planted,
                "only_control": pair.only_control,
                "only_treatment": pair.only_treatment,
            }
            for pair in comparison.pairs
        ],
    }
