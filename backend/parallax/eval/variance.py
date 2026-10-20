"""重复实验的稳定性统计。

存在的理由：Parallax 已发布的所有数字都是 **n=1**。
单次运行的优势可能只是这一次分区恰好切得均匀——评审会问，
一个从众率、覆盖率、成本都逐次波动的机制，凭什么说它的优势来自设计而不是运气。

本模块只做三件事，且刻意不做统计显著性检验：

1. 给出每个指标的 **均值 / 样本标准差 / 极差**；
2. 给出**逐次同向性**——对照组与实验组的差距在每一次重复里是否都朝同一方向；
3. 把差距与**重复间波动**放在一起比：差距若小于波动，就不能称之为稳定。

**为什么不做 t 检验**：n=3 时 t 检验的假定（近似正态）无从验证，
p 值会给人"严谨"的错觉而实际毫无效力。这里改为直接呈现区间是否重叠——
读者能自己看出结论有多脆，比一个 0.04 的 p 值诚实。
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass

from parallax.eval.experiment import ArmResult


@dataclass(frozen=True)
class Stat:
    """一组重复取值的描述统计。"""

    values: list[float]

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.values) if self.values else 0.0

    @property
    def std(self) -> float:
        """样本标准差（ddof=1）。n<2 时无定义，返回 0 并在渲染时标注。"""
        return statistics.stdev(self.values) if self.n >= 2 else 0.0

    @property
    def minimum(self) -> float:
        return min(self.values) if self.values else 0.0

    @property
    def maximum(self) -> float:
        return max(self.values) if self.values else 0.0

    @property
    def spread(self) -> float:
        """极差。比标准差更抗"只有 3 个点"的失真。"""
        return self.maximum - self.minimum

    def render(self, fmt: str = "{:.2f}") -> str:
        if self.n == 0:
            return "—"
        if self.n < 2:
            return f"{fmt.format(self.mean)}（n=1，无方差）"
        return f"{fmt.format(self.mean)} ± {fmt.format(self.std)}（极差 {fmt.format(self.spread)}）"


#: 参与稳定性统计的指标，以及它们的渲染小数位。
#: 值是 "(读取函数, 单位/格式)"，集中在一处方便与 summary.md 的列保持一致。
TRACKED: dict[str, str] = {
    "effective_channels": "{:.2f}",
    "channels_ratio": "{:.0%}",
    "redundancy": "{:.0%}",
    "coverage_fill_rate": "{:.0%}",
    "total_claims": "{:.0f}",
    "llm_calls": "{:.0f}",
    "prompt_tokens": "{:.0f}",
    "completion_tokens": "{:.0f}",
}


def _metric(result: ArmResult, name: str) -> float:
    if name == "channels_ratio":
        return result.metrics.channels_ratio
    return float(getattr(result.metrics, name))


def collect(repetitions: list[list[ArmResult]]) -> dict[str, dict[str, Stat]]:
    """把「多次重复 × 多个臂」整理成 {臂名: {指标名: Stat}}。

    某一臂在某次重复里失败时，该次不参与该臂的统计——
    把失败当 0 会把均值无端拉低，那是最容易骗过自己的算法。
    """
    raw: dict[str, dict[str, list[float]]] = {}
    for rep in repetitions:
        for result in rep:
            # run_arm/run_repo_arm 会保留失败臂的错误与占位 metrics，方便报告定位。
            # 这些 metrics 不能进入方差，否则一次 API 故障会伪装成机制退化。
            if result.errors or result.metrics.readers_failed:
                continue
            by_metric = raw.setdefault(result.metrics.arm, {})
            for name in TRACKED:
                by_metric.setdefault(name, []).append(_metric(result, name))
    return {
        arm: {name: Stat(values) for name, values in by_metric.items()}
        for arm, by_metric in raw.items()
    }


def pairwise_verdict(
    stats: dict[str, dict[str, Stat]],
    control: str,
    treatment: str,
    metric: str = "channels_ratio",
) -> list[str]:
    """逐次比较对照组与实验组，给出「优势是否稳定」的判定。

    三种可分辨的情形：
      - 差距在每次重复里都同向，且最小差距大于两者的波动之和 → **稳定**
      - 每次同向，但最小差距小于波动 → **方向一致但幅度未与噪声拉开**
      - 出现反向 → **不稳定**
    """
    if control not in stats or treatment not in stats:
        return [f"缺少 `{control}` 或 `{treatment}` 的完整重复数据，无法判定稳定性。"]
    c = stats[control].get(metric)
    t = stats[treatment].get(metric)
    if c is None or t is None or c.n < 2 or t.n < 2:
        return [
            f"重复次数不足（{control} n={c.n if c else 0}／{treatment} n={t.n if t else 0}），"
            "无法判定稳定性。"
        ]
    if c.n != t.n:
        return [
            f"两次重复的有效次数不同（{control} n={c.n}／{treatment} n={t.n}），"
            "逐次配对无意义，无法判定稳定性。"
        ]

    diffs = [b - a for a, b in zip(c.values, t.values, strict=False)]
    noise = c.std + t.std
    lines = [
        f"逐次差距（`{treatment}` − `{control}`，指标 `{metric}`）："
        + "、".join(f"{d:+.2%}" if metric == "channels_ratio" else f"{d:+.2f}" for d in diffs),
        f"对照组 {c.mean:.2%} ± {c.std:.2%}｜实验组 {t.mean:.2%} ± {t.std:.2%}"
        if metric == "channels_ratio"
        else f"对照组 {c.mean:.2f} ± {c.std:.2f}｜实验组 {t.mean:.2f} ± {t.std:.2f}",
    ]

    if all(d > 0 for d in diffs):
        if min(diffs) > noise:
            lines.append(
                f"**判定：稳定。** 每次重复都同向，且最小差距 {min(diffs):.2%} 大于两者"
                f"标准差之和 {noise:.2%}——优势幅度已与重复间波动拉开。"
            )
        else:
            lines.append(
                f"**判定：方向一致，但幅度未与噪声拉开。** 每次重复都同向（最小差距 "
                f"{min(diffs):.2%}），但该差距小于两者标准差之和 {noise:.2%}；"
                f"n={c.n} 下不能排除偶然。"
            )
    elif all(d < 0 for d in diffs):
        lines.append(f"**判定：反向且一致。** `{treatment}` 在每次重复里都低于 `{control}`。")
    else:
        lines.append("**判定：不稳定。** 出现了方向相反的重复——该指标上的差异不能归因于机制。")
    return lines


def config_drift(repetitions: list[list[ArmResult]]) -> list[str]:
    """检查**同一个臂**在不同重复之间的生效配置是否一致。

    这不是锦上添花的校验：一次真实事故就是漏传 `--readers` 导致某次重复用了默认值，
    而重复实验的全部意义在于"除随机性以外一切相同"。配置漂移会让方差里混进一个
    系统差，却仍然产出一张看上去正常的统计表。

    **按臂分别比较**，而不是把整轮的配置集合一起比：同一轮里两个臂的可见性、
    冗余系数本来就不同（那是实验设计），把整轮配置拿去比对会把每次正常运行都误报成漂移。
    """
    per_arm: dict[str, dict[str, int]] = {}
    for index, rep in enumerate(repetitions, start=1):
        for result in rep:
            if not result.config:
                continue
            key = json.dumps(result.config, ensure_ascii=False, sort_keys=True)
            per_arm.setdefault(result.metrics.arm, {}).setdefault(key, index)

    lines: list[str] = []
    for arm in sorted(per_arm):
        seen = per_arm[arm]
        if len(seen) <= 1:
            continue
        if not lines:
            lines.append("⚠️ **各次重复的生效配置不一致，本统计表不能当作方差解读。**")
        lines.append(f"  - `{arm}`：")
        for key, first_seen in seen.items():
            label = "；".join(f"{k}={v}" for k, v in sorted(json.loads(key).items()))
            lines.append(f"    - 第 {first_seen} 次重复起：{label}")
    if lines:
        lines.append("  - 修正方式：删除本目录，用同一套参数重跑全部重复。")
    return lines


def render_variance(
    repetitions: list[list[ArmResult]],
    *,
    repo: str = "",
    control: str = "baseline_shared",
    treatment: str = "blind_full",
) -> str:
    stats = collect(repetitions)
    lines = ["# 重复实验的稳定性", ""]
    if repo:
        lines.append(f"仓库：`{repo}`｜重复次数：{len(repetitions)}")
        lines.append("")

    drift = config_drift(repetitions)
    if drift:
        lines.extend(drift)
        lines.append("")

    n_ok = sum(
        1
        for rep in repetitions
        if rep and all(not result.errors and not result.metrics.readers_failed for result in rep)
    )
    failed_arms = sum(
        1 for rep in repetitions for result in rep if result.errors or result.metrics.readers_failed
    )
    lines.append(
        f"完整完成的重复：{n_ok}/{len(repetitions)}。"
        "统计口径为**样本标准差（ddof=1）**；单次失败的臂不参与该臂统计（当 0 处理会拉低均值）。"
    )
    if failed_arms:
        lines.append(f"检测到 {failed_arms} 个失败实验臂，已从统计值中排除；错误详见原始产物。")
    lines.append("")

    for arm in sorted(stats):
        lines.append(f"## `{arm}`")
        lines.append("")
        lines.append("| 指标 | 均值 ± 标准差 | 逐次取值 |")
        lines.append("| --- | --- | --- |")
        for name, fmt in TRACKED.items():
            stat = stats[arm].get(name)
            if stat is None:
                continue
            raw = "、".join(fmt.format(v) for v in stat.values)
            lines.append(f"| `{name}` | {stat.render(fmt)} | {raw} |")
        lines.append("")

    lines.append("## 优势是否稳定")
    lines.append("")
    paired = [
        [result for result in rep if result.metrics.arm in {control, treatment}]
        for rep in repetitions
    ]
    paired = [
        rep
        for rep in paired
        if {result.metrics.arm for result in rep} == {control, treatment}
        and all(not result.errors and not result.metrics.readers_failed for result in rep)
    ]
    lines.append(f"逐次比较仅使用两臂同时有效的 {len(paired)} 次重复。")
    for line in pairwise_verdict(collect(paired), control, treatment):
        lines.append(f"- {line}")
    lines.append("")
    lines.append(
        "> ⚠️ **为什么不做显著性检验**：n=3 时正态性假定无从验证，"
        "p 值会带来「严谨」的错觉而无实际效力。这里改为直接给出重复间区间，"
        "让读者自己判断结论有多脆。"
    )
    return "\n".join(lines)
