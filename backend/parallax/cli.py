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
    audit.add_argument("--max-llm-calls", type=int, default=None, help="调用次数上限，0 表示不限")
    audit.add_argument(
        "--visibility",
        choices=["blind", "shared"],
        default=None,
        help="blind = 框架正常模式；shared = 传统协作对照组",
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
    experiment.add_argument("--tasks", default=None, help="逗号分隔的任务 id，默认全部")
    experiment.add_argument("--list-arms", action="store_true", help="只列出可用实验臂后退出")
    return parser


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
    }
    return {k: v for k, v in pairs.items() if v is not None}


def _make_client(settings: Settings, dry_run: bool):
    if dry_run:
        # 空返回：只走通管线与分区，不产生 claim
        return FakeLLMClient(responder=lambda _m: {"findings": [], "notes": "dry-run"})
    if not settings.is_llm_configured():
        raise SystemExit(
            "未配置 PARALLAX_LLM_API_KEY。\n"
            "请在 backend/.env 中设置，或用 --dry-run 做离线自检。\n"
            "示例：  PARALLAX_LLM_API_KEY=sk-xxx"
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
        text = render_markdown(report)

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

    overrides = _overrides(args)
    settings = load_settings(**overrides)
    if not settings.is_llm_configured():
        raise SystemExit("未配置 PARALLAX_LLM_API_KEY（实验必须调用真实模型）")

    print(f"语料目录：{corpus_dir}")
    print(f"任务数量：{len(tasks)}｜实验臂：{len(arms)}｜总运行数：{len(tasks) * len(arms)}")
    print(f"Reader 数：{settings.n_readers}｜模型：{settings.llm_model}")
    print()

    def on_done(task, arm, result) -> None:  # noqa: ANN001
        m = result.metrics
        print(
            f"  ✓ {task.task_id}/{arm.name:24s} 召回 {m.hits}/{m.planted}"
            f"｜claims {m.total_claims:3d}｜K*={m.effective_channels}"
            f"｜轮次 {m.rounds}｜{result.elapsed_s}s"
        )

    results = await run_experiment(tasks, settings, arms=arms, on_arm_done=on_done)

    base = Path(args.out) if args.out else _framework_root() / "eval" / "results"
    out_dir = base if args.out else default_out_dir(base)
    summary_path = save_results(results, out_dir)

    print()
    print(render_summary(results, arms))
    print(f"\n结果已写入：{out_dir}")
    print(f"摘要：{summary_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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
    parser.error(f"未知命令 {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
