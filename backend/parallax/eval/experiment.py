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

import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from parallax.config import Settings
from parallax.domain.models import Claim
from parallax.engine import ParallaxEngine
from parallax.eval.corpus import GroundTruth, Task
from parallax.eval.metrics import ArmMetrics, compute_metrics
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from parallax.ports.llm import LLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Arm:
    """一个实验配置。

    后两个字段是**真实预算**，不是“维度数量”代理：
    成本-质量前沿必须能横铺多个预算档，而 `initial_focus_count` 只能调首轮维度数，
    两者算出的是不同东西。为 None 时沿用全局配置。
    """

    name: str
    description: str
    visibility: str
    redundancy_factor: str  # "one" = 1；"half" = ceil(n/2)；"all" = n
    max_rounds: int
    initial_focus_count: int = 0
    """首轮限制为前 K 个维度（0 = 不限）。用于固定预算对照。"""
    max_llm_calls: int | None = None
    """调用次数上限；None = 沿用全局设置。"""
    max_tokens: int | None = None
    """总 token 预算；None = 沿用全局设置。"""

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
        name="sharded_blind",
        description="分片与 sharded_shared 相同且均为单轮，只隔离同伴输出可见性",
        visibility="blind",
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
    # 该臂产出的全部 claim（未截断）。报告按档位只渲染前 40 条（已加显式提示），
    # 但结论质量抽查必须从完整集合里抽样——只从报告抽会偏向高置信，使结论不可外推。
    claims: list[Claim] = field(default_factory=list)
    reader_evidence: dict[str, list[str]] = field(default_factory=dict)
    """每个 Reader 实际读到的证据 id，落盘成 `<task>__<arm>.readers.json`。

    为什么必须单独落盘：`reader_units` 只有条数，而「三个 Reader 读同一批」与
    「三个 Reader 读不同批」的条数可以完全相同。集中 vs 分散的对照全靠这个区别，
    不把 id 存下来就无法事后核验。
    """
    config: dict = field(default_factory=dict)
    """该臂的**生效配置**快照。

    必须随产物一起落盘：配置只出现在终端输出里的话，终端一滚就没人知道
    这批数字是在什么设置下跑出来的。真实事故——一次重复实验漏传 `--readers`，
    用了默认 3 而头条数字来自 6，两者 K\\* 的上限不同，却看上去同样正常。
    """


def config_snapshot(settings: Settings, **extra: object) -> dict:
    """记录那些**会改变指标含义**的设置。

    刻意不含 API key、超时这类"不影响结论"的项：快照要能被一眼读完，
    塞满无关字段等于没有快照。
    """
    snapshot: dict[str, object] = {
        "model": settings.llm_model,
        "reasoning_effort": settings.llm_reasoning_effort,
        "readers": settings.n_readers,
        "redundancy": settings.redundancy,
        "support_threshold": settings.support_threshold,
        "max_rounds": settings.max_rounds,
        "visibility": settings.reader_visibility,
        "seed": settings.seed,
        "max_evidence_per_call": settings.max_evidence_per_call,
        "max_units_per_reader": settings.max_units_per_reader,
        "equal_exposure": settings.equal_exposure,
        "max_batch_chars": settings.llm_max_batch_chars,
        "max_output_tokens": settings.llm_max_output_tokens,
        "max_llm_calls": settings.max_llm_calls,
        "max_tokens": settings.max_tokens,
        "min_independent_support": settings.effective_min_independent_support(),
        "max_evidence_overlap_rate": settings.max_evidence_overlap_rate,
        "adaptive_scheduling": settings.adaptive_scheduling,
        "llm_falsifier": settings.enable_llm_falsifier,
        "semantic_partitioning": settings.semantic_partitioning,
        "partition_assignment": settings.partition_assignment,
    }
    try:
        repo = Path(__file__).resolve().parents[3]
        snapshot["git_revision"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        digest = hashlib.sha256()
        for source in sorted((repo / "backend" / "parallax").rglob("*.py")):
            digest.update(source.relative_to(repo).as_posix().encode())
            digest.update(source.read_bytes())
        snapshot["implementation_sha256"] = digest.hexdigest()
    except (OSError, subprocess.SubprocessError):
        snapshot["git_revision"] = "unavailable"
    snapshot.update({k: v for k, v in extra.items() if v not in (None, "")})
    return snapshot


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
    # 预算只在臂里显式给出时才覆盖全局值——否则会把全局设置默默改掉。
    if arm.max_llm_calls is not None:
        overrides["max_llm_calls"] = arm.max_llm_calls
    if arm.max_tokens is not None:
        overrides["max_tokens"] = arm.max_tokens
    return Settings(**overrides)


def expand_budgets(
    arms: list[Arm],
    *,
    calls: list[int] | None = None,
    tokens: list[int] | None = None,
) -> list[Arm]:
    """把预算档与实验臂做笛卡尔积，名字后缀带档位。

    预算作为独立维度而不写死在 `ARMS` 里：前沿需要 3 档以上，
    固定枚举会让臂表膨胀，也会与已有的 8 个臂名混淆。
    """
    call_levels: list[int | None] = list(calls) if calls else [None]
    token_levels: list[int | None] = list(tokens) if tokens else [None]
    if call_levels == [None] and token_levels == [None]:
        return list(arms)
    expanded: list[Arm] = []
    for arm in arms:
        for call_level in call_levels:
            for token_level in token_levels:
                suffix = ""
                if call_level is not None:
                    suffix += f"@calls{call_level}"
                if token_level is not None:
                    suffix += f"@tokens{token_level}"
                expanded.append(
                    replace(
                        arm,
                        name=arm.name + suffix,
                        max_llm_calls=call_level,
                        max_tokens=token_level,
                    )
                )
    return expanded


async def run_arm(
    task: Task,
    arm: Arm,
    base_settings: Settings,
    client_factory,
    group_depth: int = 2,
) -> ArmResult:
    """在一个任务上跑一个实验臂。

    `group_depth` 属于**证据适配器**的粒度参数，不属于机制本身，但它直接决定了
    分区是否均衡：实测各切片在深度 2 下只有 4~5 个分组，3 个 Reader 分 4 个组时
    必然撞车（最坏 1/25/0）。做「每人预算相同」的受控对比时必须调到 3，
    并配合 `partition_assignment=greedy`，否则分区不均会被读成机制效应。
    """
    settings = make_settings(base_settings, arm)
    client: LLMClient = client_factory(settings)
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(
            task.repo_path,
            extensions=(".py",),
            group_depth=group_depth,
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
        reader_evidence=dict(engine.runtime.pool.reader_evidence),
        split_retries=engine.runtime.pool.split_retries,
        dropped_chunks=engine.runtime.pool.dropped_chunks,
    )

    from parallax.reporting import render_markdown

    if engine.runtime.pool.failed_readers:
        errors.append(f"Reader failures: {len(engine.runtime.pool.failed_readers)}")
    if hasattr(client, "aclose"):
        await client.aclose()  # type: ignore[attr-defined]

    return ArmResult(
        metrics=metrics,
        elapsed_s=round(elapsed, 2),
        report_markdown=render_markdown(report, max_items=settings.report_max_items),
        errors=errors,
        claims=list(claims),
        reader_evidence=dict(engine.runtime.pool.reader_evidence),
        config=config_snapshot(settings, task=task.task_id, group_depth=group_depth),
    )


async def run_experiment(
    tasks: list[Task],
    base_settings: Settings,
    arms: list[Arm] | None = None,
    client_factory=None,
    on_arm_done=None,
    group_depth: int = 2,
) -> list[ArmResult]:
    """在所有任务 × 所有实验臂上跑一遍。"""
    arms = arms or ARMS
    factory = client_factory or (lambda s: OpenAICompatClient(s))
    results: list[ArmResult] = []

    for task in tasks:
        for arm in arms:
            logger.info("══ 任务 %s ｜ 实验臂 %s ══", task.task_id, arm.name)
            result = await run_arm(
                task, arm, base_settings, factory, group_depth=group_depth
            )
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


def _render_reader_units(m: ArmMetrics) -> str:
    """每 Reader 实读单元数 —— **判断曝光量操纵是否生效的落点**。

    集中臂：几个 Reader 的数字相同且远小于语料规模；
    分散臂：数字之和覆盖全集。只印总调用数会把两者混成同一个数字，
    此前 P2 冒烟就是这样把「读完以后的预算耗尽」误读成「受预算限制」。
    """
    if not m.reader_units:
        return "—"
    per = "/".join(str(v) for v in m.reader_units.values())
    return f"{per} → 合并 {m.reader_union}"


def _render_integrity(m: ArmMetrics) -> str:
    """测量通道完整性。**丢批不为 0 的臂，召回不能与另一臂比较。**

    这一列存在的唯一目的：让「两臂失败数不等」在汇总表上就看得见。
    2026-10-29 的 S2 集中臂 12 次调用丢了 7 次，召回 4/10 是残值，
    而这个事实当时只躺在日志里，于是被读成了「分散更差」。
    """
    if m.dropped_chunks is None:
        # 旧产物没有这个字段。**不能当成健康**——那会把事故痕迹抹掉。
        return "—（旧产物未记录）"
    if m.dropped_chunks:
        return f"⚠ 丢批 {m.dropped_chunks}"
    if m.split_retries:
        return f"拆批 {m.split_retries}"
    return "OK"


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
        reader_evidence=dict(engine.runtime.pool.reader_evidence),
        split_retries=engine.runtime.pool.split_retries,
        dropped_chunks=engine.runtime.pool.dropped_chunks,
    )

    from parallax.reporting import render_markdown

    if engine.runtime.pool.failed_readers:
        errors.append(f"Reader failures: {len(engine.runtime.pool.failed_readers)}")
    if hasattr(client, "aclose"):
        await client.aclose()  # type: ignore[attr-defined]

    return ArmResult(
        metrics=metrics,
        elapsed_s=round(elapsed, 2),
        report_markdown=render_markdown(report, max_items=settings.report_max_items),
        errors=errors,
        claims=list(claims),
        config=config_snapshot(
            settings,
            repo=task.repo_path.name,
            group_depth=group_depth,
            max_files=max_files,
        ),
    )


def _render_config(results: list[ArmResult]) -> str:
    """把**生效配置**写进汇总表本身。

    存在的理由是一次真实事故：一次重复实验漏传了 `--readers`，于是它用了默认 3 而
    头条数字来自 6，两者 Agent 数不同、口径不可比，而那批产物看上去完全正常。
    配置只出现在终端输出里是不够的——终端会滚掉，产物会留下来。
    """
    configs = {
        json.dumps(r.config, ensure_ascii=False, sort_keys=True) for r in results if r.config
    }
    if not configs:
        return ""
    parts = []
    for raw in sorted(configs):
        config = json.loads(raw)
        label = "；".join(f"{k}={v}" for k, v in sorted(config.items()) if v not in (None, ""))
        parts.append(f"- {label}" if len(configs) > 1 else f"- 生效配置：{label}")
    return "**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）\n\n" + "\n".join(
        parts
    )


def render_summary(results: list[ArmResult], arms: list[Arm] | None = None) -> str:
    arms = arms or ARMS
    descriptions = {a.name: a.description for a in arms}

    lines = ["# 对照实验结果", ""]
    lines.append(f"生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(_render_config(results))
    lines.append("")
    lines.append("")

    lines.append("## 主指标对照")
    lines.append("")
    lines.append(
        "| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） | 完整性 |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |"
    )
    for result in results:
        m = result.metrics
        lines.append(
            f"| `{m.arm}` | {_render_recall(m)} | {_render_precision(m)} | "
            f"{m.redundancy:.0%} | {m.effective_channels} / {m.agent_count} | "
            f"{m.channels_ratio:.0%} | {m.coverage_fill_rate:.0%} | "
            f"{m.rounds} | {m.llm_calls} | {m.readers_failed} | {_render_reader_units(m)} | "
            f"{_render_integrity(m)} |"
        )
    lines.append("")
    broken = [m.metrics.arm for m in results if m.metrics.dropped_chunks]
    if broken:
        lines.append(
            "> ⚠️ **以下实验臂丢弃了批次，其召回是残值，不得与另一臂比较**："
            + "、".join(f"`{name}`" for name in broken)
            + "。丢批来自模型把单次输出预算烧在推理上、正文为空；拆到单文件仍失败才会丢。"
        )
        lines.append("")
    lines.append(
        "> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** "
        "若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，"
        "此时两臂的召回差异**不能**归因于分配方式。"
    )
    lines.append("")

    if any(m.metrics.recall is None for m in results):
        lines.append(
            "> **召回率与精确率为 `N/A` 说明该任务没有 ground truth。** "
            "输出 K\\* 描述指纹重叠结构，不能证明事实正确或取证独立；"
            "它与报告中按证据分区计算的独立性画像是两种指标。"
        )
        lines.append("")

    agent_counts = {m.metrics.agent_count for m in results if m.metrics.agent_count}
    if len(agent_counts) > 1:
        lines.append(
            "> ⚠️ **本表各臂的 Agent 数不同，请勿直接比较裸 K\\*。** "
            "表中 N 只计产出者，排除了零产出的 Reader；同时报告非空分区 Reader 数、"
            "分区、轮数和 tokens。归一化本身不能消除预算或选择偏差。"
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
        # 耗时只在确实记录过时才印。从 metrics.json 重新渲染时它是未知的，
        # 印成 "0.0s" 会被误读成"瞬间完成"。
        elapsed = f"- 耗时 {result.elapsed_s}s｜" if result.elapsed_s else "- "
        lines.append(
            f"{elapsed}LLM 调用 {m.llm_calls} 次"
            f"（输入 {m.prompt_tokens} / 输出 {m.completion_tokens} tokens）"
            f"｜失败 {m.llm_failures}｜schema 重试 {m.schema_retries}"
            f"｜Reader 失败 {m.readers_failed}"
        )
        lines.append(f"- 停止原因 `{m.stop_reason}`｜轮次 {m.rounds}")
        if m.assigned_reader_count is not None:
            lines.append(
                f"- 非空分区 Reader {m.assigned_reader_count}｜产出 Claim 的 Reader {m.agent_count}｜输出 K*/已分配 Reader {m.assigned_channels_ratio:.1%}"
            )
        if m.reader_units:
            per = "、".join(f"{k}={v}" for k, v in m.reader_units.items())
            lines.append(f"- 每 Reader 实读单元：{per}｜合并去重 {m.reader_union}")
        distinct = (
            str(m.distinct_fingerprints)
            if m.distinct_fingerprints is not None
            else "—（旧产物未记录）"
        )
        lines.append(
            f"- claim 总数 {m.total_claims}"
            f"（独立指纹 {distinct}｜冗余率 {m.redundancy:.0%}"
            f"｜未匹配 {m.unmatched}）"
        )
        if m.recall is None:
            lines.append("- 命中情况：**无 ground truth，跳过**（召回/精确不适用）")
        else:
            missed = m.missed_ids()
            lines.append(
                f"- 命中 {m.hits}/{m.planted} 个植入缺陷"
                f"｜命中同一缺陷的重复 claim {m.duplicates} 条"
            )
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
        # 同时落 elapsed_s 与 errors：口径修正后要能在**不重跑实验**的前提下
        # 重新渲染 summary.md。此前只存 metrics，导致每次改口径都要重花几美元。
        "arms": [
            {
                **json.loads(r.metrics.model_dump_json()),
                "elapsed_s": r.elapsed_s,
                "errors": r.errors,
                "config": r.config,
                "valid": not r.errors and r.metrics.readers_failed == 0,
            }
            for r in results
        ],
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for result in results:
        if result.report_markdown:
            name = f"{result.metrics.task_id}__{result.metrics.arm}.md"
            (out_dir / name).write_text(result.report_markdown, encoding="utf-8")
        if result.reader_evidence:
            # 每 Reader 实读的证据 id：集中 vs 分散的可核验落点，必须落盘
            rname = f"{result.metrics.task_id}__{result.metrics.arm}.readers.json"
            (out_dir / rname).write_text(
                json.dumps(result.reader_evidence, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if result.claims is not None:
            # 完整 claim 清单：抽查与后续分析的事实来源，不受报告的 40 条展示上限影响
            payload = [
                {
                    "claim_id": c.claim_id,
                    "fingerprint": c.fingerprint,
                    "statement": c.statement,
                    "claim_type": c.claim_type,
                    "polarity": c.polarity.value,
                    "severity": c.metadata.get("severity"),
                    "stance": c.metadata.get("stance"),
                    "extracted_by": c.extracted_by,
                    "round_index": c.round_index,
                    "verified_by": c.verified_by,
                    "disputed_with": c.disputed_with,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "locator": c.source_refs[0].locator if c.source_refs else None,
                    "rationale": c.metadata.get("rationale"),
                    "title": c.metadata.get("title"),
                    "line_start": c.metadata.get("line_start"),
                    "line_end": c.metadata.get("line_end"),
                    "verification_status": c.verification_status,
                    "independent_support": c.metadata.get("independent_support"),
                    "source_refs": [ref.model_dump(mode="json") for ref in c.source_refs],
                }
                for c in result.claims
            ]
            cname = f"{result.metrics.task_id}__{result.metrics.arm}.claims.json"
            (out_dir / cname).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    return out_dir / "summary.md"


def default_out_dir(base: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return base / stamp


def rerender_summary(out_dir: Path, arms: list[Arm] | None = None) -> Path:
    """从 `metrics.json` 重建 `summary.md`，不重跑实验。

    存在的理由：汇总口径已经改过两次（K\\* 可比性、两种"冗余"混用），
    每次都要重跑实验才能刷新一个表格是不可接受的——一次两臂运行要几美元和近一小时。
    """
    raw = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    results = [
        ArmResult(
            metrics=ArmMetrics.model_validate(entry),
            elapsed_s=entry.get("elapsed_s", 0.0),
            errors=entry.get("errors", []),
            config=entry.get("config", {}),
        )
        for entry in raw["arms"]
    ]
    summary_path = out_dir / "summary.md"
    summary_path.write_text(render_summary(results, arms), encoding="utf-8")
    return summary_path
