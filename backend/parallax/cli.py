"""命令行入口。

    parallax audit <repo> [--question ...] [--readers N] [--redundancy K]
                          [--visibility blind|shared] [--json] [--out FILE]

设计意图：让框架**开箱即可运行**，不必先写 Python 代码。
「可部署、可运行、可测试」是评审明确看的维度，一个能直接敲命令跑起来的入口
比任何架构图都有说服力。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from parallax.config import Settings, load_settings
from parallax.engine import ParallaxEngine
from parallax.infra.llm_fake import FakeLLMClient
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from parallax.reporting import render_markdown, summarise

DEFAULT_QUESTION = "找出这个代码仓库中真实存在的缺陷，并说明触发条件。"


def _framework_root() -> Path:
    """框架根目录。

    cli.py 位于 <framework>/backend/parallax/cli.py，所以往上是三级。
    ⚠️ 这里曾经写成 parents[3]（= 框架的父目录），导致实验结果被写到框架外面，
    违反「一切产物只存在于框架目录内」的约束。改路径时务必核对层级。
    """
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parallax",
        description="Parallax —— 抗从众的多智能体证据装配框架",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="对本地代码仓库执行多智能体独立审查")
    audit.add_argument("repo", help="代码仓库根目录")
    audit.add_argument("--question", default=DEFAULT_QUESTION)
    audit.add_argument("--extensions", default=".py", help="逗号分隔的扩展名，如 .py,.ts")
    audit.add_argument("--group-depth", type=int, default=2, help="模块分组深度")
    audit.add_argument("--max-files", type=int, default=300)

    audit.add_argument("--readers", type=int, default=None, help="Reader 数量")
    audit.add_argument("--redundancy", type=int, default=None, help="每条证据被几个 Reader 看到")
    audit.add_argument("--support", type=int, default=None, help="判定高置信所需的独立来源数")
    audit.add_argument("--max-rounds", type=int, default=None)
    audit.add_argument(
        "--semantic-partitioning", action=argparse.BooleanOptionalAction, default=None
    )
    audit.add_argument("--max-llm-calls", type=int, default=None, help="调用次数上限，0 表示不限")
    audit.add_argument(
        "--visibility",
        choices=["blind", "shared"],
        default=None,
        help="blind = 框架正常模式；shared = 传统协作对照组",
    )
    audit.add_argument(
        "--llm-falsifier",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="启用独立真实模型反证（默认跟随 PARALLAX_ENABLE_LLM_FALSIFIER）",
    )
    audit.add_argument(
        "--adaptive-scheduling",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="启用缺口优先的确定性补检调度（默认跟随 PARALLAX_ADAPTIVE_SCHEDULING）",
    )

    audit.add_argument(
        "--arbitrator",
        choices=["null", "blind", "llm", "llm-blind"],
        default=None,
        help=(
            "争议仲裁器：null=不仲裁（默认）；blind=规则型结论剥离；"
            "llm=模型仲裁；llm-blind=模型仲裁但不把结论交给模型"
        ),
    )
    audit.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    audit.add_argument("--out", default=None, help="把报告写入文件")
    audit.add_argument(
        "--dry-run",
        action="store_true",
        help="不调用模型，仅检查证据加载与分区（用于离线自检）",
    )

    experiment = sub.add_parser(
        "experiment",
        help="在植入缺陷语料上跑对照实验（对照组 vs 实验组 + 消融）",
    )
    experiment.add_argument(
        "--corpus",
        default=None,
        help="语料目录（默认 <repo>/eval/corpus）",
    )
    experiment.add_argument(
        "--out", default=None, help="结果输出目录（默认 eval/results/<时间戳>）"
    )
    experiment.add_argument(
        "--arms",
        default=None,
        help="逗号分隔的实验臂名，默认全部（见 experiment 帮助）",
    )
    experiment.add_argument("--readers", type=int, default=None, help="Reader 数量")
    experiment.add_argument(
        "--group-depth",
        type=int,
        default=2,
        help="模块分组深度（证据适配器粒度）。默认 2 与历史结果一致；"
        "但深度 2 下各切片只有 4~5 个分组，做「每人预算相同」的对比时分区会严重不均，"
        "此时应改用 3 并配 --partition-assignment greedy",
    )
    experiment.add_argument(
        "--equal-exposure",
        action="store_true",
        default=None,
        help="每人曝光量自动取 ceil(语料条数 / Reader 数)：集中臂大家读同一批 N/R，"
        "分散臂各读不同批、合并覆盖全集。这是「每人预算相同」受控对比的正确姿势",
    )
    experiment.add_argument("--tasks", default=None, help="逗号分隔的任务 id，默认全部")
    experiment.add_argument("--list-arms", action="store_true", help="只列出可用实验臂后退出")
    experiment.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="重复次数。>1 时每次重复独立成子目录，并另出 variance.md（稳定性统计）",
    )
    experiment.add_argument(
        "--budget-calls",
        default=None,
        help="总调用次数上限（不是单次输出长度），逗号分隔多档（如 8,24）；"
        "预算耗尽的臂会提前停止，召回会被低估，解读时必须看 stop_reason",
    )
    experiment.add_argument(
        "--budget-tokens",
        default=None,
        help="总 token 预算（不是单次输出上限，那个是 PARALLAX_LLM_MAX_OUTPUT_TOKENS），"
        "逗号分隔多档；达到预算后引擎停止",
    )
    experiment.add_argument(
        "--max-units-per-reader",
        type=int,
        default=None,
        help="单个 Reader **整轮**最多读几条证据（0=不限）。这是曝光量上限，"
        "与单次调用条数（max_evidence_per_call）不是一回事；"
        "集中臂设 N 后所有 Reader 读同一批 N 条，分散臂通常不会被截断",
    )
    experiment.add_argument(
        "--partition-assignment",
        choices=["hash", "greedy"],
        default=None,
        help="分组到 Reader 的分配算法。hash（默认）=旧行为；greedy=按负载贪心均衡，"
        "分组数少（如 4 个组配 3 个 Reader）时必须用它，否则会分出空转的 Reader",
    )
    experiment.add_argument(
        "--variance-control",
        default=None,
        help="variance.md 里的对照臂名（默认取所选的前两条臂）",
    )
    experiment.add_argument("--variance-treatment", default=None, help="variance.md 里的实验臂名")

    real = sub.add_parser(
        "real",
        help="在**真实代码仓库**上跑对照实验（无 ground truth，只测 K*/冗余/覆盖率/成本）",
    )
    real.add_argument(
        "repos",
        nargs="+",
        help="一个或多个仓库目录路径",
    )
    real.add_argument(
        "--arms",
        default="baseline_shared,blind_full",
        help="逗号分隔的实验臂名，默认 baseline_shared,blind_full",
    )
    real.add_argument("--readers", type=int, default=None, help="Reader 数量")
    real.add_argument(
        "--group-depth", type=int, default=2, help="模块分组深度（真实仓库目录更深，可调）"
    )
    real.add_argument("--max-files", type=int, default=300, help="每个仓库最多扫描多少文件")
    real.add_argument("--out", default=None, help="结果输出目录（默认 eval/real/<时间戳>）")
    real.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="重复次数。>1 时每次重复独立成子目录，并另出 variance.md（稳定性统计）",
    )
    real.add_argument(
        "--visibility", default=None, choices=["blind", "shared"], help="覆盖可见性（一般不用）"
    )

    rerender = sub.add_parser(
        "rerender",
        help="从已有运行的 metrics.json 重建 summary.md（不重跑实验、不调模型）",
    )
    rerender.add_argument("run_dir", help="包含 metrics.json 的结果目录")

    spotcheck = sub.add_parser(
        "spotcheck",
        help="从完整 claim 集分层抽样，产出结论质量抽查工作表（不调模型）",
    )
    spotcheck.add_argument(
        "claims",
        nargs="+",
        help="一个或多个 *.claims.json（由 save_results 落盘，含未截断的全部 claim）",
    )
    spotcheck.add_argument("--out", required=True, help="工作表输出目录")
    spotcheck.add_argument("--seed", type=int, default=20261016, help="随机种子（保证可复核）")
    spotcheck.add_argument(
        "--quota",
        default=None,
        help="各档抽样条数，形如 high_confidence=15,pending=15,disputed=10",
    )
    receipt = sub.add_parser("receipts", help="导入并审计外部编排器的 Receipt bundle JSON")
    receipt.add_argument("bundle", type=Path)
    receipt.add_argument("--out", type=Path)

    stats = sub.add_parser(
        "stats",
        help="对已有 metrics.json 做配对统计（McNemar、自助法区间、Holm），不调模型",
    )
    stats.add_argument(
        "runs",
        nargs="+",
        help="一个或多个 metrics.json（也接受包含 metrics.json 的目录）",
    )
    stats.add_argument("--control", default="baseline_shared", help="对照组臂名")
    stats.add_argument("--treatment", default="blind_full", help="实验组臂名")
    stats.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    stats.add_argument("--resamples", type=int, default=20000, help="自助法重采样次数")
    stats.add_argument("--seed", type=int, default=20261028, help="随机种子（保证可复算）")
    stats.add_argument("--out", type=Path, default=None, help="报告与 JSON 输出目录")
    return parser


def _int_list(raw: str | None) -> list[int] | None:
    """解析逗号分隔的预算档；空值返回 None，非法值直接报错而不是静默忽略。"""
    if not raw:
        return None
    values: list[int] = []
    for part in raw.split(","):
        text = part.strip()
        if not text:
            continue
        try:
            value = int(text)
        except ValueError as exc:
            raise SystemExit(f"预算档必须是整数：{text}") from exc
        if value <= 0:
            raise SystemExit(f"预算档必须为正数：{value}")
        values.append(value)
    return values or None


def _overrides(args: argparse.Namespace) -> dict:
    """从命令行参数收集配置覆盖项。

    用 getattr 而不是直接取属性：audit 与 experiment 两个子命令的参数集不同，
    直接访问会抛 AttributeError。
    """
    pairs = {
        "n_readers": getattr(args, "readers", None),
        "redundancy": getattr(args, "redundancy", None),
        "support_threshold": getattr(args, "support", None),
        "max_rounds": getattr(args, "max_rounds", None),
        "max_llm_calls": getattr(args, "max_llm_calls", None),
        "reader_visibility": getattr(args, "visibility", None),
        "enable_llm_falsifier": getattr(args, "llm_falsifier", None),
        "adaptive_scheduling": getattr(args, "adaptive_scheduling", None),
        "semantic_partitioning": getattr(args, "semantic_partitioning", None),
        "arbitrator": getattr(args, "arbitrator", None),
        "max_units_per_reader": getattr(args, "max_units_per_reader", None),
        "partition_assignment": getattr(args, "partition_assignment", None),
        "equal_exposure": getattr(args, "equal_exposure", None),
    }
    return {k: v for k, v in pairs.items() if v is not None}


def _make_client(settings: Settings, dry_run: bool):
    if dry_run:
        # 空返回：只走通管线与分区，不产生 claim
        return FakeLLMClient(responder=lambda _m: {"findings": [], "notes": "dry-run"})
    if not settings.is_llm_configured():
        raise SystemExit(
            "未配置模型 API Key（PARALLAX_LLM_API_KEY 或 OPENAI_API_KEY）。\n"
            "请在 backend/.env 中设置，或用 --dry-run 做离线自检。\n"
            "示例：  OPENAI_API_KEY=sk-xxx"
        )
    return OpenAICompatClient(settings)


async def _run_audit(args: argparse.Namespace) -> int:
    settings = load_settings(**_overrides(args))
    adapter = RepoAdapter(
        Path(args.repo),
        extensions=tuple(e.strip() for e in args.extensions.split(",") if e.strip()),
        group_depth=args.group_depth,
        max_files=args.max_files,
    )
    client = _make_client(settings, args.dry_run)
    engine = ParallaxEngine.build(
        adapter=adapter,
        plugin=CodeAuditReader(),
        client=client,
        settings=settings,
    )

    report = await engine.run(args.question)

    if hasattr(client, "aclose"):
        await client.aclose()  # type: ignore[attr-defined]

    if args.json:
        payload = json.loads(report.model_dump_json())
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = render_markdown(report, max_items=settings.report_max_items)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"报告已写入 {out_path}")
    else:
        print(text)

    print(f"\n[摘要] {summarise(report)}")
    print(f"[用量] {engine.usage_snapshot()}")
    return 0


async def _run_experiment_cli(args: argparse.Namespace) -> int:
    from parallax.eval.corpus import load_corpus, verify_task
    from parallax.eval.experiment import (
        ARMS,
        default_out_dir,
        expand_budgets,
        render_summary,
        run_experiment,
        save_results,
    )

    if args.list_arms:
        for arm in ARMS:
            print(f"{arm.name:26s} {arm.description}")
        return 0

    if args.corpus:
        corpus_dir = Path(args.corpus)
    else:
        corpus_dir = _framework_root() / "eval" / "corpus"

    tasks = load_corpus(corpus_dir)
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        tasks = [t for t in tasks if t.task_id in wanted]
        if not tasks:
            raise SystemExit(f"没有匹配的任务：{sorted(wanted)}")

    # 语料完整性自检：行号漂移会让召回率静默变成 0，必须前置拦下
    for task in tasks:
        problems = verify_task(task)
        if problems:
            raise SystemExit(
                f"语料 {task.task_id} 自检失败，请修正 ground_truth.json：\n  - "
                + "\n  - ".join(problems)
            )

    arms = ARMS
    if args.arms:
        wanted = {a.strip() for a in args.arms.split(",") if a.strip()}
        arms = [a for a in ARMS if a.name in wanted]
        if not arms:
            raise SystemExit(f"没有匹配的实验臂：{sorted(wanted)}")

    calls = _int_list(args.budget_calls)
    tokens = _int_list(args.budget_tokens)
    arms = expand_budgets(arms, calls=calls, tokens=tokens)

    overrides = _overrides(args)
    settings = load_settings(**overrides)
    if not settings.is_llm_configured():
        raise SystemExit(
            "未配置模型 API Key（PARALLAX_LLM_API_KEY 或 OPENAI_API_KEY，实验必须调用真实模型）"
        )

    print(f"语料目录：{corpus_dir}")
    print(
        f"任务数量：{len(tasks)}｜实验臂：{len(arms)}｜重复：{args.repeat} 次"
        f"｜总运行数：{len(tasks) * len(arms) * args.repeat}"
    )
    if calls or tokens:
        print(f"预算档：调用 {calls or '—'}｜token {tokens or '—'}")
    print(f"Reader 数：{settings.n_readers}｜模型：{settings.llm_model}")
    print()

    def on_done(task, arm, result) -> None:  # noqa: ANN001
        m = result.metrics
        print(
            f"  ✓ {task.task_id}/{arm.name:24s} 召回 {m.hits}/{m.planted}"
            f"｜claims {m.total_claims:3d}｜K*={m.effective_channels}"
            f"｜轮次 {m.rounds}｜{result.elapsed_s}s"
        )

    base = Path(args.out) if args.out else _framework_root() / "eval" / "results"
    out_dir = base if args.out else default_out_dir(base)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 每次重复独立成目录，产物可逐次核对，而不是只留一个被平均过的总表。
    repetitions: list[list] = []
    for rep_index in range(1, args.repeat + 1):
        rep_dir = out_dir if args.repeat == 1 else out_dir / f"rep{rep_index}"
        rep_dir.mkdir(parents=True, exist_ok=True)
        if args.repeat > 1:
            print(f"══ 第 {rep_index}/{args.repeat} 次重复 ══")

        results = await run_experiment(
            tasks, settings, arms=arms, on_arm_done=on_done, group_depth=args.group_depth
        )
        if not results:
            raise SystemExit("没有任何成功的实验臂")

        summary_path = save_results(results, rep_dir)
        print(render_summary(results, arms))
        print(f"\n第 {rep_index} 次结果已写入：{rep_dir}")
        print(f"摘要：{summary_path}")
        repetitions.append(results)

    if args.repeat > 1:
        from parallax.eval.variance import render_variance

        variance_kwargs = {"repo": ", ".join(task.task_id for task in tasks)}
        control, treatment = args.variance_control, args.variance_treatment
        if control is None and treatment is None:
            if len(arms) == 2:
                control, treatment = arms[0].name, arms[1].name
                print(f"稳定性统计比较 `{control}` 与 `{treatment}`")
            else:
                print(
                    "提示：实验臂不是恰好 2 条，请用 --variance-control/"
                    "--variance-treatment 指定要比较的两条，否则 variance.md 无法给出判定"
                )
        if control:
            variance_kwargs["control"] = control
        if treatment:
            variance_kwargs["treatment"] = treatment
        (out_dir / "variance.md").write_text(
            render_variance(repetitions, **variance_kwargs), encoding="utf-8"
        )
        print(f"\n稳定性统计：{out_dir / 'variance.md'}")
    return 0


async def _run_real_cli(args: argparse.Namespace) -> int:
    """在真实仓库上跑对照实验。

    与 `experiment` 子命令的关键差别：**没有 ground truth**。
    因此不报告召回率/精确率（标为 N/A），只报告不需要标尺就能测的指标——
    K*、冗余率、覆盖率、成本。这不是缩水：K* 由 Agent 之间的重叠矩阵算出，
    本来就不需要知道哪条结论是对的。
    """
    from parallax.eval.experiment import (
        ARMS,
        default_out_dir,
        render_summary,
        run_repo_arm,
        save_results,
    )

    arms = ARMS
    if args.arms:
        wanted = {a.strip() for a in args.arms.split(",") if a.strip()}
        arms = [a for a in ARMS if a.name in wanted]
        if not arms:
            raise SystemExit(f"没有匹配的实验臂：{sorted(wanted)}")

    repos: list[Path] = []
    for raw in args.repos:
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            raise SystemExit(f"仓库目录不存在：{path}")
        repos.append(path)

    overrides = _overrides(args)
    settings = load_settings(**overrides)
    if not settings.is_llm_configured():
        raise SystemExit(
            "未配置模型 API Key（PARALLAX_LLM_API_KEY 或 OPENAI_API_KEY，真实仓库实验必须调用真实模型）"
        )

    print("真实仓库对照实验（无 ground truth）")
    print(f"仓库：{len(repos)} 个｜实验臂：{len(arms)} 个｜重复：{args.repeat} 次")
    print(f"总运行数：{len(repos) * len(arms) * args.repeat}")
    print(f"Reader 数：{settings.n_readers}｜模型：{settings.llm_model}")
    print(f"分组深度：{args.group_depth}｜文件上限：{args.max_files}")
    print()

    base = Path(args.out) if args.out else _framework_root() / "eval" / "real"
    out_dir = base if args.out else default_out_dir(base)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 每次重复独立成目录：产物可逐次核对，而不是只留一个被平均过的总表。
    repetitions: list[list] = []
    for rep_index in range(1, args.repeat + 1):
        rep_dir = out_dir if args.repeat == 1 else out_dir / f"rep{rep_index}"
        rep_dir.mkdir(parents=True, exist_ok=True)
        if args.repeat > 1:
            print(f"══ 第 {rep_index}/{args.repeat} 次重复 ══")

        results: list = []
        for repo in repos:
            print(f"── {repo.name} ──")
            for arm in arms:
                try:
                    result = await run_repo_arm(
                        repo,
                        arm,
                        settings,
                        lambda s: OpenAICompatClient(s),
                        group_depth=args.group_depth,
                        max_files=args.max_files,
                    )
                except Exception as exc:  # noqa: BLE001 - 单臂失败不阻断其余
                    print(f"  ✗ {arm.name:24s} {type(exc).__name__}: {exc}")
                    continue
                m = result.metrics
                flag = "" if m.readers_failed == 0 else f"｜⚠️ Reader 失败 {m.readers_failed}"
                print(
                    f"  ✓ {arm.name:24s} claims {m.total_claims:3d}"
                    f"｜K*={m.effective_channels:.2f}"
                    f"／{m.agent_count}"
                    f"｜占比 {m.channels_ratio:.0%}"
                    f"｜冗余 {m.redundancy:.0%}"
                    f"｜覆盖 {m.coverage_fill_rate:.0%}"
                    f"｜轮次 {m.rounds}"
                    f"｜调用 {m.llm_calls}"
                    f"｜{result.elapsed_s}s{flag}"
                )
                results.append(result)
            print()

        if not results:
            raise SystemExit("没有任何成功的实验臂")

        summary_path = save_results(results, rep_dir)
        print(render_summary(results, arms))
        print(f"\n第 {rep_index} 次结果已写入：{rep_dir}")
        print(f"摘要：{summary_path}")
        repetitions.append(results)

    if args.repeat > 1:
        from parallax.eval.variance import render_variance

        repo_label = ", ".join(r.name for r in repos)
        (out_dir / "variance.md").write_text(
            render_variance(repetitions, repo=repo_label), encoding="utf-8"
        )
        print(f"\n稳定性统计：{out_dir / 'variance.md'}")
    return 0


def _run_rerender_cli(args: argparse.Namespace) -> int:
    from parallax.eval.experiment import rerender_summary

    run_dir = Path(args.run_dir)
    if not (run_dir / "metrics.json").exists():
        raise SystemExit(f"{run_dir} 下没有 metrics.json")
    summary_path = rerender_summary(run_dir)
    print(f"已重建：{summary_path}")
    return 0


def _run_stats_cli(args: argparse.Namespace) -> int:
    """对已有产物做配对统计。不调模型、不重跑实验。"""
    import json as _json

    from parallax.eval.stats import (
        collect_comparisons,
        comparison_payload,
        render_report,
    )

    paths: list[Path] = []
    for raw in args.runs:
        path = Path(raw).expanduser()
        if path.is_dir():
            candidate = path / "metrics.json"
            if not candidate.exists():
                raise SystemExit(f"{path} 下没有 metrics.json")
            paths.append(candidate)
        elif path.is_file():
            paths.append(path)
        else:
            raise SystemExit(f"路径不存在：{path}")

    comparisons, skipped = collect_comparisons(
        paths,
        args.control,
        args.treatment,
        resamples=args.resamples,
        seed=args.seed,
        alpha=args.alpha,
    )
    if not comparisons:
        raise SystemExit(
            f"没有可比较的运行：需要同一份 metrics.json 同时包含 "
            f"`{args.control}` 与 `{args.treatment}`，且任务带 ground truth。\n"
            + ("\n".join(skipped) if skipped else "")
        )

    report = render_report(comparisons, alpha=args.alpha, source=", ".join(str(p) for p in paths))
    for label in skipped:
        report += f"\n> 跳过：{label}"
    print(report)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "stats.md").write_text(report, encoding="utf-8")
        payload = {
            "control": args.control,
            "treatment": args.treatment,
            "alpha": args.alpha,
            "seed": args.seed,
            "comparisons": [
                {"label": label, **comparison_payload(comparison)}
                for label, comparison in comparisons
            ],
        }
        (args.out / "stats.json").write_text(
            _json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n已写入：{args.out / 'stats.md'}、{args.out / 'stats.json'}")
    return 0


def _run_spotcheck_cli(args: argparse.Namespace) -> int:
    """产出抽查工作表。刻意不调模型——这一步是给人看的清单。"""
    from parallax.eval.spotcheck import write_outputs

    quota = None
    if args.quota:
        quota = {}
        for part in args.quota.split(","):
            key, _, value = part.partition("=")
            if not key.strip() or not value.strip().isdigit():
                raise SystemExit(f"--quota 格式应为 key=N，收到：{part}")
            quota[key.strip()] = int(value)

    out_dir = Path(args.out)
    for raw in args.claims:
        claims_path = Path(raw)
        if not claims_path.exists():
            raise SystemExit(f"找不到 claim 文件：{claims_path}")
        worksheet, _ = write_outputs(claims_path, out_dir, per_bucket=quota, seed=args.seed)
        print(f"已生成：{worksheet}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "receipts":
        from parallax.ports.receipts import ReceiptBundle

        if args.bundle.stat().st_size > 50_000_000:
            raise SystemExit("Receipt bundle 超过 50 MB")
        bundle = ReceiptBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
        text = json.dumps(bundle.audit(), ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0
    if args.command == "audit":
        try:
            return asyncio.run(_run_audit(args))
        except KeyboardInterrupt:
            print("已中断", file=sys.stderr)
            return 130
    if args.command == "experiment":
        try:
            return asyncio.run(_run_experiment_cli(args))
        except KeyboardInterrupt:
            print("已中断", file=sys.stderr)
            return 130
    if args.command == "real":
        try:
            return asyncio.run(_run_real_cli(args))
        except KeyboardInterrupt:
            print("已中断", file=sys.stderr)
            return 130
    if args.command == "rerender":
        return _run_rerender_cli(args)
    if args.command == "stats":
        return _run_stats_cli(args)
    if args.command == "spotcheck":
        return _run_spotcheck_cli(args)
    parser.error(f"未知命令 {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
