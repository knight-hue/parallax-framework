"""对照实验编排。

## 五个实验臂，以及它们各自隔离出什么

实验设计的关键是**一次只动一个变量**，否则指标差异无法归因。

| 臂名 | 每人分到的证据 | 同伴结论可见 | 补检 | 隔离出什么 |
|---|---|---|---|---|
| `baseline_shared` | 全部 | 是 | 否 | **传统多智能体协作基线** |
| `sharded_shared` | 与实验组相同 | **是** | 否 | **公平对照**：分片相同，只差共享 |
| `no_peers_all_evidence` | 全部 | 否 | 否 | 「所有人读全部、但互不可见」 |
| `blind_no_coverage` | 互斥（redundancy=1） | 否 | 否 | 严格分区、不给补检帮忙 |
| `blind_full`（本框架） | 与 sharded_shared 相同 | 否 | **是** | 完整机制 |

两条干净的因果链：

    sharded_shared  →  blind_full         隔离出「同伴可见性 + 补检」
    baseline_shared →  no_peers_all_evidence → blind_full   隔离出「读多少」与「怎么读」

## 为什么要单独设 `sharded_shared`

第一版设计只有 `baseline_shared` 作为对照，但它**同时**改变了两件事：
每人读多少（全部 vs 分片）、以及能否看到同伴结论。
更麻烦的是，要求「所有人都读全部」会让单次输出超出模型的 token 上限
（2712 行语料实测会截断），于是对照组的召回损失里混进了「输出被砍」这个工程原因。

`sharded_shared` 把分片大小对齐后，两者唯一的差别就是**能否看到同伴结论**，
归因才是干净的。被截断的对照仍然保留，但它的定位变成「带宽受限下的基线」，
而不是机制比较的基准。

## 对照的公平性

同一份插件、同一份提示词、同一个模型、同一个种子，只翻转配置开关。
对照组不是另写一套脚本——如果两组跑在两套代码上，任何差异都无法排除「实现差异」这个替代解释。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from parallax.config import Settings
from parallax.engine import ParallaxEngine
from parallax.eval.corpus import GroundTruth, Task
from parallax.eval.metrics import ArmMetrics, compute_metrics
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from parallax.ports.llm import LLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Arm:
    """一个实验配置。"""

    name: str
    description: str
    visibility: str
    redundancy_factor: str  # "one" = 1；"half" = ceil(n/2)；"all" = n
    max_rounds: int
    initial_focus_count: int = 0
    """首轮限制为前 K 个维度（0 = 不限）。用于固定预算对照。"""

    def redundancy(self, n_readers: int) -> int:
        if self.redundancy_factor == "one":
            return 1
        if self.redundancy_factor == "all":
            return n_readers
        return max(1, (n_readers + 1) // 2)


ARMS: list[Arm] = [
    Arm(
        name="baseline_shared",
        description="传统多智能体：所有人看全部证据 + 可见彼此结论",
        visibility="shared",
        redundancy_factor="all",
        max_rounds=1,
    ),
    Arm(
        name="sharded_shared",
        description="公平对照：分片大小与实验组完全相同，但可见彼此结论（隔离出「共享」单独的效果）",
        visibility="shared",
        redundancy_factor="half",
        max_rounds=1,
    ),
    Arm(
        name="no_peers_all_evidence",
        description="所有人看全部证据，但看不到彼此结论",
        visibility="blind",
        redundancy_factor="all",
        max_rounds=1,
    ),
    Arm(
        name="blind_no_coverage",
        description="严格互斥分区，关闭补检（redundancy=1, max_rounds=1）",
        visibility="blind",
        redundancy_factor="one",
        max_rounds=1,
    ),
    Arm(
        name="blind_full",
        description="本框架完整机制：受控冗余分区 + 覆盖率驱动补检",
        visibility="blind",
        redundancy_factor="half",
        max_rounds=3,
    ),
    Arm(
        name="budget_shared",
        description="固定预算对照：每 Reader 预算相同，但所有人读同样的 K 个维度并共享结论",
        visibility="shared",
        redundancy_factor="all",
        max_rounds=1,
        initial_focus_count=1,
    ),
    Arm(
        name="budget_blind",
        description="固定预算实验组：每 Reader 预算相同，各读不同的维度（联合覆盖 n 倍）",
        visibility="blind",
        redundancy_factor="one",
        max_rounds=1,
    ),
]


@dataclass
class ArmResult:
    metrics: ArmMetrics
    elapsed_s: float = 0.0
    report_markdown: str = ""
    errors: list[str] = field(default_factory=list)


def make_settings(base: Settings, arm: Arm) -> Settings:
    overrides = base.model_dump()
    overrides.update(
        {
            "reader_visibility": arm.visibility,
            "redundancy": arm.redundancy(base.n_readers),
            "max_rounds": arm.max_rounds,
            "initial_focus_count": arm.initial_focus_count,
        }
    )
    return Settings(**overrides)


async def run_arm(
    task: Task,
    arm: Arm,
    base_settings: Settings,
    client_factory,
) -> ArmResult:
    """在一个任务上跑一个实验臂。"""
    settings = make_settings(base_settings, arm)
    client: LLMClient = client_factory(settings)
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(
            task.repo_path,
            extensions=(".py",),
            group_depth=2,
        ),
        plugin=CodeAuditReader(),
        client=client,
        settings=settings,
    )

    started = time.perf_counter()
    errors: list[str] = []
    try:
        report = await engine.run(task.question)
    except Exception as exc:  # noqa: BLE001 - 单个臂失败不应中断整轮实验
        logger.exception("实验臂 %s 在任务 %s 上失败", arm.name, task.task_id)
        errors.append(f"{type(exc).__name__}: {exc}")
        from parallax.domain.models import Report, RunManifest

        report = Report(
            run_id=f"failed-{arm.name}",
            question=task.question,
            manifest=RunManifest(
                run_id=f"failed-{arm.name}",
                question=task.question,
                plugin="code_audit",
                seed=settings.seed,
                max_rounds=settings.max_rounds,
                support_threshold=settings.support_threshold,
            ),
        )
    elapsed = time.perf_counter() - started

    claims = engine.runtime.ledger.claims
    metrics = compute_metrics(
        arm=arm.name,
        task_id=task.task_id,
        report=report,
        claims=claims,
        defects=task.ground_truth.defects,
        usage=engine.usage_snapshot(),
        reader_count=settings.n_readers,
        readers_failed=len(engine.runtime.pool.failed_readers),
    )

    from parallax.reporting import render_markdown

    if hasattr(client, "aclose"):
        await client.aclose()  # type: ignore[attr-defined]

    return ArmResult(
        metrics=metrics,
        elapsed_s=round(elapsed, 2),
        report_markdown=render_markdown(report),
        errors=errors,
    )


async def run_experiment(
    tasks: list[Task],
    base_settings: Settings,
    arms: list[Arm] | None = None,
    client_factory=None,
    on_arm_done=None,
) -> list[ArmResult]:
    """在所有任务 × 所有实验臂上跑一遍。"""
    arms = arms or ARMS
    factory = client_factory or (lambda s: OpenAICompatClient(s))
    results: list[ArmResult] = []

    for task in tasks:
        for arm in arms:
            logger.info("══ 任务 %s ｜ 实验臂 %s ══", task.task_id, arm.name)
            result = await run_arm(task, arm, base_settings, factory)
            results.append(result)
            if on_arm_done:
                on_arm_done(task, arm, result)
    return results


# ---- 报告 ----


def _render_recall(m: ArmMetrics) -> str:
    """召回率单元格。无 ground truth 时显示 N/A，而不是伪装成 0%。"""
    if m.recall is None:
        return "N/A"
    return f"{m.recall:.0%} ({m.hits}/{m.planted})"


def _render_precision(m: ArmMetrics) -> str:
    if m.precision is None:
        return "N/A"
    return f"{m.precision:.0%}"


# ---- 真实仓库（无 ground truth）----

REAL_REPO_QUESTION = "找出这个代码仓库中真实存在的缺陷，并说明触发条件。"


def make_repo_task(
    repo_path: str | Path,
    *,
    task_id: str | None = None,
    question: str = REAL_REPO_QUESTION,
) -> Task:
    """把一个真实代码仓库包装成 Task——**带一个空的 ground truth**。

    这不是"作弊式复用"，而是刻意的：让真实仓库走与合成语料**完全相同**的执行路径，
    唯一差别就是 `defects=[]`。如果为真实仓库另写一条执行链，
    那两边的结果就不可比了，而"可比"正是这项验证的全部意义。
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"仓库目录不存在：{root}")
    return Task(
        task_id=task_id or root.name,
        root=root,
        repo_path=root,
        ground_truth=GroundTruth(task_id=task_id or root.name, description="真实仓库（无标注）"),
        question=question,
    )


async def run_repo_arm(
    repo_path: str | Path,
    arm: Arm,
    base_settings: Settings,
    client_factory,
    *,
    group_depth: int = 2,
    max_files: int = 300,
    task_id: str | None = None,
) -> ArmResult:
    """在真实仓库上跑一个实验臂。

    与 `run_arm` 的区别只有两处：适配器参数可调（真实仓库目录结构更深、文件更多），
    以及 ground truth 为空。
    """
    task = make_repo_task(repo_path, task_id=task_id)
    settings = make_settings(base_settings, arm)
    client: LLMClient = client_factory(settings)
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(
            task.repo_path,
            extensions=(".py",),
            group_depth=group_depth,
            max_files=max_files,
        ),
        plugin=CodeAuditReader(),
        client=client,
        settings=settings,
    )

    started = time.perf_counter()
    errors: list[str] = []
    try:
        report = await engine.run(task.question)
    except Exception as exc:  # noqa: BLE001 - 单臂失败不应中断整轮
        logger.exception("真实仓库实验臂 %s 在 %s 上失败", arm.name, task.task_id)
        errors.append(f"{type(exc).__name__}: {exc}")
        from parallax.domain.models import Report, RunManifest

        report = Report(
            run_id=f"failed-{arm.name}",
            question=task.question,
            manifest=RunManifest(
                run_id=f"failed-{arm.name}",
                question=task.question,
                plugin="code_audit",
                seed=settings.seed,
                max_rounds=settings.max_rounds,
                support_threshold=settings.support_threshold,
            ),
        )
    elapsed = time.perf_counter() - started

    claims = engine.runtime.ledger.claims
    metrics = compute_metrics(
        arm=arm.name,
        task_id=task.task_id,
        report=report,
        claims=claims,
        defects=(),  # ← 真实仓库没有标注
        usage=engine.usage_snapshot(),
        reader_count=settings.n_readers,
        readers_failed=len(engine.runtime.pool.failed_readers),
    )

    from parallax.reporting import render_markdown

    if hasattr(client, "aclose"):
        await client.aclose()  # type: ignore[attr-defined]

    return ArmResult(
        metrics=metrics,
        elapsed_s=round(elapsed, 2),
        report_markdown=render_markdown(report),
        errors=errors,
    )


def render_summary(results: list[ArmResult], arms: list[Arm] | None = None) -> str:
    arms = arms or ARMS
    descriptions = {a.name: a.description for a in arms}

    lines = ["# 对照实验结果", ""]
    lines.append(f"生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}")
    lines.append("")

    lines.append("## 主指标对照")
    lines.append("")
    lines.append(
        "| 实验臂 | 召回率 | 精确率 | 冗余率 | 有效独立通道 K* / Agent 数 | 独立通道占比 | 覆盖率 | 轮次 | 调用 | Reader 失败 |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for result in results:
        m = result.metrics
        lines.append(
            f"| `{m.arm}` | {_render_recall(m)} | {_render_precision(m)} | "
            f"{m.redundancy:.0%} | {m.effective_channels} / {m.agent_count} | "
            f"{m.channels_ratio:.0%} | {m.coverage_fill_rate:.0%} | "
            f"{m.rounds} | {m.llm_calls} | {m.readers_failed} |"
        )
    lines.append("")

    if any(m.metrics.recall is None for m in results):
        lines.append(
            "> **召回率与精确率为 `N/A` 说明该任务没有 ground truth。** "
            "这不会削弱 K\\* 的价值——它由 Agent 之间的**重叠矩阵**算出，"
            "不需要知道哪条结论是对的，因此是这类无标注任务上唯一仍可测的核心指标。"
        )
        lines.append("")

    agent_counts = {m.metrics.agent_count for m in results if m.metrics.agent_count}
    if len(agent_counts) > 1:
        lines.append(
            "> ⚠️ **本表各臂的 Agent 数不同，请勿直接比较裸 K\\*。** "
            "每一轮都会生成全新 Reader 身份（这是补检不破坏盲读的前提），"
            "所以 3 轮 × 6 Reader 的臂实际有 18 个 Agent，它的 K\\* 上限是 18 而不是 6。"
            "跨臂比较应看 **K\\*/N 占比**，或只比较 Agent 数相同的臂。"
        )
        lines.append("")

    # 无标注时逐缺陷矩阵无意义（没有缺陷可比）
    if results and results[0].metrics.defects:
        lines.append("## 逐缺陷命中矩阵")
        lines.append("")
        lines.append("每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，")
        lines.append("被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。")
        lines.append("")
        defect_ids = [d.defect_id for d in results[0].metrics.defects]
        header = "| 实验臂 | " + " | ".join(defect_ids) + " | 孤证数 | 漏检 |"
        lines.append(header)
        lines.append("| --- | " + " | ".join("---:" for _ in defect_ids) + " | ---: | ---: |")
        for result in results:
            m = result.metrics
            cells = []
            for defect in m.defects:
                cells.append(str(len(defect.found_by)) if defect.hit else "✗")
            lines.append(
                f"| `{m.arm}` | " + " | ".join(cells) + f" | {m.sole_source_defects} | "
                f"{len(m.missed_ids())} |"
            )
        lines.append("")

    lines.append("## 实验臂说明")
    lines.append("")
    for arm in arms:
        lines.append(f"- `{arm.name}`：{descriptions.get(arm.name, '')}")
    lines.append("")

    lines.append("## 明细")
    lines.append("")
    for result in results:
        m = result.metrics
        lines.append(f"### `{m.arm}`")
        lines.append("")
        lines.append(
            f"- 耗时 {result.elapsed_s}s｜LLM 调用 {m.llm_calls} 次"
            f"（输入 {m.prompt_tokens} / 输出 {m.completion_tokens} tokens）"
            f"｜失败 {m.llm_failures}｜schema 重试 {m.schema_retries}"
            f"｜Reader 失败 {m.readers_failed}"
        )
        lines.append(f"- 停止原因 `{m.stop_reason}`｜轮次 {m.rounds}")
        lines.append(
            f"- claim 总数 {m.total_claims}"
            f"（独立指纹 {m.total_claims - m.duplicates}｜冗余 {m.duplicates}"
            f"｜未匹配 {m.unmatched}）"
        )
        if m.recall is None:
            lines.append("- 命中情况：**无 ground truth，跳过**（召回/精确不适用）")
        else:
            missed = m.missed_ids()
            lines.append(f"- 漏检：{', '.join(missed) if missed else '无'}")
        if result.errors:
            lines.append(f"- ⚠️ 错误：{'; '.join(result.errors)}")
        lines.append("")
    return "\n".join(lines)


def save_results(results: list[ArmResult], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = render_summary(results)
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")

    raw = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "arms": [json.loads(r.metrics.model_dump_json()) for r in results],
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for result in results:
        if result.report_markdown:
            name = f"{result.metrics.task_id}__{result.metrics.arm}.md"
            (out_dir / name).write_text(result.report_markdown, encoding="utf-8")

    return out_dir / "summary.md"


def default_out_dir(base: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return base / stamp
