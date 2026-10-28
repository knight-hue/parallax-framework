"""后台审查任务的编排。

## 为什么是「提交即返回」而不是同步等待

一次审查要跑几十秒到几分钟。同步 HTTP 会撞上网关/浏览器的超时，
而且用户看不到中间过程。所以提交后立刻返回 run_id，
进度通过 `GET /audits/{run_id}/events` 的 SSE 流实时推送。

## 任务并发

每个运行是一个 `asyncio.Task`。`max_concurrent_runs` 限制同时运行的数量——
LLM 有并发上限，无节制地放任务只会让所有任务一起超时。
超出的任务保持在 `queued` 状态，由调度器在有空位时启动。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from parallax.config import Settings
from parallax.core.reputation import SQLiteReputationStore
from parallax.domain.errors import ConfigurationError
from parallax.engine import ParallaxEngine
from parallax.infra.falsifier_llm import LLMFalsifier
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.infra.object_store import build_object_store
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from parallax.ports.reproduction import DockerReproductionExecutor
from parallax.reporting import render_markdown, summarise
from parallax.service.artifacts import mirror_run_artifacts
from parallax.service.callback import CompletionCallback
from parallax.service.events import RunEventBus
from parallax.service.sources import RepoSourceManager, validate_commit_sha, validate_git_url
from parallax.service.store import RunRecord, RunStore
from parallax.service.trace import current_trace_id
from parallax.util import stable_id

logger = logging.getLogger(__name__)

DEFAULT_QUESTION = "找出这个代码仓库中真实存在的缺陷，并说明触发条件。"


@dataclass(frozen=True)
class AuditJob:
    """一次审查任务的全部输入。

    刻意做成显式对象，而不是把适配器参数挂在 Settings 上：
    Settings 是**框架配置**（会影响机制行为），适配器参数是**插件参数**（只影响读哪些文件）。
    混在一起会让"改了这个设置会改变什么"变得不可推理，也难以为实验复现留痕。
    """

    run_id: str
    repo_path: Path | None
    question: str
    settings: Settings
    repo_url: str | None = None
    commit_sha: str | None = None
    extensions: tuple[str, ...] = (".py",)
    group_depth: int = 2
    max_files: int = 300
    trace_id: str | None = None
    credential_id: str | None = None


class AuditRunner:
    """审查任务的提交与执行。"""

    def __init__(
        self,
        store: RunStore,
        bus: RunEventBus,
        settings: Settings,
        client_factory: Callable[[Settings], object] | None = None,
        max_concurrent_runs: int = 2,
    ) -> None:
        self.store = store
        self.bus = bus
        self.settings = settings
        self.max_concurrent_runs = max_concurrent_runs
        self.artifacts = build_object_store(
            kind=settings.artifact_store,
            local_root=settings.artifact_local_root or (store.root / "_artifacts"),
            bucket=settings.artifact_s3_bucket,
            prefix=settings.artifact_s3_prefix,
            endpoint_url=settings.artifact_s3_endpoint,
            region=settings.artifact_s3_region,
            access_key=settings.artifact_s3_access_key,
            secret_key=settings.artifact_s3_secret_key,
        )
        self._client_factory = client_factory or (lambda s: OpenAICompatClient(s))
        self._callback = CompletionCallback(settings)
        # 声誉跨运行累积，不能随每个 HTTP 任务重新创建内存字典。
        # SQLite 保持单机/共享卷部署的持久性，替换存储实现不会影响引擎协议。
        self._reputation_store = SQLiteReputationStore(store.root / "reputation.sqlite3")
        self._sources = RepoSourceManager(store.root / ".sources")
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)

    # ---- 提交 ----

    def submit(
        self,
        *,
        repo_path: str | None,
        overrides: dict,
        trace_id: str | None = None,
        credential_id: str | None = None,
    ) -> RunRecord:
        """登记一次运行并安排执行。立即返回。"""
        requested_path = Path(repo_path).expanduser() if repo_path else None
        repo_url = str(overrides.get("repo_url") or "").strip() or None
        commit_sha = validate_commit_sha(overrides.get("commit_sha"))
        if requested_path is None and repo_url is None:
            raise ConfigurationError("repo_path 或 repo_url 至少提供一个")
        repo = requested_path.resolve() if requested_path is not None else None
        if repo is not None and not repo.is_dir():
            raise ConfigurationError(f"仓库路径不存在或不是目录：{repo}")
        if repo_url:
            repo_url = validate_git_url(repo_url)
        if repo is not None and self.settings.audit_root.strip():
            root = Path(self.settings.audit_root).expanduser().resolve()
            if repo != root and root not in repo.parents:
                raise ConfigurationError(f"仓库路径必须位于允许的审查根目录内：{root}")

        settings = self._merge_settings(overrides)
        job = AuditJob(
            run_id=stable_id(
                str(repo or repo_url),
                commit_sha or "HEAD",
                settings.n_readers,
                settings.redundancy,
                settings.support_threshold,
                settings.max_rounds,
                settings.reader_visibility,
                datetime.now(UTC).timestamp(),  # 允许同一路径重复审查
            ),
            repo_path=repo,
            repo_url=repo_url,
            commit_sha=commit_sha,
            question=overrides.get("question") or DEFAULT_QUESTION,
            settings=settings,
            extensions=tuple(overrides.get("extensions") or (".py",)),
            group_depth=int(overrides.get("group_depth") or 2),
            max_files=int(overrides.get("max_files") or 300),
            # traceId 取显式传入的；没传就沿用当前上下文（网关的请求头会写进去）
            trace_id=trace_id or current_trace_id(),
            credential_id=credential_id,
        )

        record = RunRecord(
            run_id=job.run_id,
            status="queued",
            question=job.question,
            repo_path=str(job.repo_path) if job.repo_path else "",
            repo_url=job.repo_url,
            commit_sha=job.commit_sha,
            trace_id=job.trace_id,
            credential_id=job.credential_id,
            settings_snapshot={
                "readers": settings.n_readers,
                "redundancy": settings.redundancy,
                "support_threshold": settings.support_threshold,
                "max_rounds": settings.max_rounds,
                "visibility": settings.reader_visibility,
                "model": settings.llm_model,
                "extensions": list(job.extensions),
                "group_depth": job.group_depth,
                "max_files": job.max_files,
                "repo_url": job.repo_url,
                "commit_sha": job.commit_sha,
                "enable_llm_falsifier": settings.enable_llm_falsifier,
                "adaptive_scheduling": settings.adaptive_scheduling,
                "semantic_partitioning": settings.semantic_partitioning,
                "min_independent_support": settings.min_independent_support,
                "max_evidence_overlap_rate": settings.max_evidence_overlap_rate,
            },
        )
        self.store.create(record)
        self.bus.publish(
            job.run_id,
            "queued",
            {
                "run_id": job.run_id,
                "repo_path": str(job.repo_path) if job.repo_path else None,
                "repo_url": job.repo_url,
                "commit_sha": job.commit_sha,
                "settings": record.settings_snapshot,
            },
        )

        self._schedule(job)
        return record

    def _schedule(self, job: AuditJob) -> None:
        """把已落盘的任务放入当前进程执行。

        先写 ``queued`` 再创建 Task，服务进程在任意时刻退出时都能从
        RunStore 找回任务。任务本身只保存在内存，恢复入口见 ``recover``。
        """
        if job.run_id in self._tasks and not self._tasks[job.run_id].done():
            return
        task = asyncio.create_task(self._guarded_run(job))
        self._tasks[job.run_id] = task
        task.add_done_callback(lambda _t, rid=job.run_id: self._tasks.pop(rid, None))

    def recover(self) -> int:
        """恢复上次进程退出时遗留的 queued/running 任务。

        ``running`` 任务没有可靠的跨进程锁，不能假设原 Worker 仍存在，
        因此统一重新排队；run_id 保持不变，结果和计费仍然幂等。
        """
        recovered = 0
        for record in self.store.list(limit=10_000):
            if record.status not in {"queued", "running"}:
                continue
            if self.store.lease_active(
                record.run_id, lease_seconds=self.settings.worker_lease_seconds
            ):
                # 另一个副本仍在执行；不能把它抢回来造成双重模型调用。
                continue
            repo = Path(record.repo_path) if record.repo_path else None
            if not record.repo_url and (repo is None or not repo.is_dir()):
                self.store.update(
                    record.run_id,
                    status="failed",
                    finished_at=_now(),
                    error=f"服务恢复时仓库路径不可用：{repo or record.repo_url}",
                )
                self.bus.publish(record.run_id, "failed", {"error": "仓库路径不可用"})
                self.bus.close(record.run_id)
                continue
            if record.status == "running":
                self.store.update(
                    record.run_id,
                    status="queued",
                    error="服务重启后自动重新排队",
                    started_at=None,
                    finished_at=None,
                )
            snapshot = record.settings_snapshot
            settings = self._settings_from_snapshot(snapshot)
            job = AuditJob(
                run_id=record.run_id,
                repo_path=repo,
                repo_url=record.repo_url,
                commit_sha=record.commit_sha or snapshot.get("commit_sha"),
                question=record.question or DEFAULT_QUESTION,
                settings=settings,
                extensions=tuple(snapshot.get("extensions") or (".py",)),
                group_depth=int(snapshot.get("group_depth") or 2),
                max_files=int(snapshot.get("max_files") or 300),
                trace_id=record.trace_id,
                credential_id=record.credential_id,
            )
            self.bus.publish(record.run_id, "recovered", {"run_id": record.run_id})
            self._schedule(job)
            recovered += 1
        return recovered

    # ---- 执行 ----

    async def _guarded_run(self, job: AuditJob) -> None:
        try:
            async with self._semaphore:
                if not self.store.claim(
                    job.run_id, lease_seconds=self.settings.worker_lease_seconds
                ):
                    logger.info("运行 %s 已被其他 worker 领取，跳过本地副本", job.run_id)
                    return
                heartbeat = asyncio.create_task(self._heartbeat(job.run_id))
                try:
                    await self._run(job)
                finally:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)
                    self.store.release(job.run_id)
        except asyncio.CancelledError:
            # CancelledError 继承 BaseException，不会被 _run 的普通异常分支捕获。
            # 这里必须显式落终态，否则重启恢复会把用户主动取消当成僵尸任务。
            if (current := self.store.get(job.run_id)) is None or current.status != "canceled":
                self.store.update(
                    job.run_id,
                    status="canceled",
                    finished_at=_now(),
                    error="任务被请求取消",
                )
                self.bus.publish(job.run_id, "canceled", {"run_id": job.run_id})
                self.bus.close(job.run_id)
            await self._callback.report(
                run_id=job.run_id,
                credential_id=job.credential_id,
                status="canceled",
                prompt_tokens=0,
                completion_tokens=0,
            )
            raise

    async def _heartbeat(self, run_id: str) -> None:
        interval = max(1.0, self.settings.worker_lease_seconds / 3.0)
        try:
            while True:
                await asyncio.sleep(interval)
                self.store.refresh_lease(run_id)
        except asyncio.CancelledError:
            return

    def cancel(self, run_id: str) -> RunRecord | None:
        """请求取消一次运行；重复取消是幂等的。"""
        record = self.store.get(run_id)
        if record is None:
            return None
        if record.status in {"done", "failed", "canceled"}:
            return record
        task = self._tasks.get(run_id)
        if task is None:
            updated = self.store.update(
                run_id, status="canceled", finished_at=_now(), error="任务被请求取消"
            )
            self.bus.publish(run_id, "canceled", {"run_id": run_id})
            self.bus.close(run_id)
            return updated
        # 先落盘再取消 Task。若任务尚未被事件循环首次调度，
        # Python 不会进入 CancelledError 处理分支，提前写终态可避免永久 queued。
        self.store.update(run_id, status="canceled", finished_at=_now(), error="任务被请求取消")
        self.bus.publish(run_id, "canceled", {"run_id": run_id})
        self.bus.close(run_id)
        task.cancel()
        return self.store.get(run_id)

    async def _run(self, job: AuditJob) -> None:
        run_id = job.run_id
        started = time.perf_counter()
        self.store.update(run_id, status="running", started_at=_now())
        self.bus.publish(run_id, "started", {"run_id": run_id, "question": job.question})

        client = None
        try:
            source = await asyncio.to_thread(
                self._sources.resolve,
                run_id=run_id,
                repo_path=job.repo_path,
                repo_url=job.repo_url,
                commit_sha=job.commit_sha,
            )
            self.store.update(
                run_id,
                repo_path=str(source.path),
                repo_url=source.source_url,
                commit_sha=source.commit_sha,
            )
            client = self._client_factory(job.settings)
            falsifier = (
                LLMFalsifier(client, max_evidence_chars=job.settings.falsifier_max_evidence_chars)
                if job.settings.enable_llm_falsifier
                else None
            )
            engine = ParallaxEngine.build(
                adapter=RepoAdapter(
                    source.path,
                    extensions=job.extensions,
                    group_depth=job.group_depth,
                    max_files=job.max_files,
                ),
                plugin=CodeAuditReader(),
                client=client,  # type: ignore[arg-type]
                settings=job.settings,
                reproduction_executor=(
                    DockerReproductionExecutor(
                        source.path,
                        image=job.settings.reproduction_image,
                        timeout_s=job.settings.reproduction_timeout_s,
                    )
                    if job.settings.enable_reproduction
                    else None
                ),
                reputation_store=self._reputation_store,
                falsifier=falsifier,
            )
            # 把编排内部的进度事件直接接进总线（同一条事件流，前端无需区分来源）
            engine.runtime.event_sink = lambda event_type, payload: self.bus.publish(
                run_id, event_type, payload
            )
            report = await engine.run(job.question, run_id=run_id)
        except Exception as exc:  # noqa: BLE001 - 任何失败都要落到运行记录里
            logger.exception("运行 %s 失败", run_id)
            elapsed = round(time.perf_counter() - started, 2)
            self.store.update(
                run_id,
                status="failed",
                finished_at=_now(),
                elapsed_s=elapsed,
                error=f"{type(exc).__name__}: {exc}",
            )
            self.bus.publish(run_id, "failed", {"error": f"{type(exc).__name__}: {exc}"})
            self.bus.close(run_id)
            if client is not None and hasattr(client, "aclose"):
                await client.aclose()  # type: ignore[attr-defined]
            # 失败也要回报：网关已经为这次提交扣了额度，
            # 不回传的话它会永远停在 queued，报表上成为一条永远不结束的运行。
            await self._callback.report(
                run_id=run_id,
                credential_id=job.credential_id,
                status="failed",
                prompt_tokens=0,
                completion_tokens=0,
                elapsed_s=elapsed,
            )
            return

        elapsed = round(time.perf_counter() - started, 2)
        usage = engine.usage_snapshot()

        self.store.save_report(
            run_id, render_markdown(report, max_items=job.settings.report_max_items)
        )
        summary = _summary_payload(report, engine)
        self.store.save_summary(run_id, summary)
        self.store.save_claims(run_id, engine.runtime.ledger.claims)
        mirror_run_artifacts(
            self.artifacts,
            run_id,
            markdown=render_markdown(report, max_items=job.settings.report_max_items),
            summary=summary,
            claims=engine.runtime.ledger.claims,
        )
        self.store.save_manifest(run_id, report.manifest)
        self.store.save_source_hashes(
            run_id,
            {
                u.locator: u.metadata["sha256"]
                for u in engine.runtime.evidence
                if "sha256" in u.metadata
            },
        )
        self.store.update(
            run_id,
            status="done",
            finished_at=_now(),
            elapsed_s=elapsed,
            counts=report.counts(),
            rounds=len(report.manifest.rounds),
            stop_reason=report.manifest.stop_reason.value if report.manifest.stop_reason else None,
            llm_calls=usage["calls"],
            readers_failed=len(engine.runtime.pool.failed_readers),
        )
        self.bus.publish(
            run_id,
            "done",
            {
                "summary": summarise(report),
                "counts": report.counts(),
                "elapsed_s": elapsed,
                "usage": usage,
            },
        )
        self.bus.close(run_id)

        if hasattr(client, "aclose"):
            await client.aclose()  # type: ignore[attr-defined]

        # 回报用量。放在最后且失败只记 WARN——记账是平台层的事，
        # 不该反过来把一次成功的审查变成失败。
        await self._callback.report(
            run_id=run_id,
            credential_id=job.credential_id,
            status="done",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            elapsed_s=elapsed,
            stop_reason=report.manifest.stop_reason.value if report.manifest.stop_reason else None,
            counts=report.counts(),
        )

    # ---- 生命周期 ----

    async def shutdown(self) -> None:
        """等待在跑的任务收敛（优雅停机）。

        强行取消会在磁盘上留下 status=running 的僵尸记录，
        所以这里选择等待而不是 cancel，由调用方给一个超时。
        """
        tasks = [t for t in self._tasks.values() if not t.done()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())

    # ---- 内部 ----

    def _merge_settings(self, overrides: dict) -> Settings:
        """把请求里的机制旋钮合并进服务默认配置。只认白名单键，避免任意字段被远程改写。"""
        base = self.settings.model_dump()
        allowed = {
            "readers": "n_readers",
            "redundancy": "redundancy",
            "support_threshold": "support_threshold",
            "max_rounds": "max_rounds",
            "visibility": "reader_visibility",
            "reader_visibility": "reader_visibility",
            "enable_llm_falsifier": "enable_llm_falsifier",
            "adaptive_scheduling": "adaptive_scheduling",
            "semantic_partitioning": "semantic_partitioning",
            "min_independent_support": "min_independent_support",
            "max_evidence_overlap_rate": "max_evidence_overlap_rate",
        }
        for key, target in allowed.items():
            value = overrides.get(key)
            if value is not None:
                base[target] = value
        return Settings(**base)

    def _settings_from_snapshot(self, snapshot: dict) -> Settings:
        """按任务落盘时的机制参数恢复 Settings，模型沿用当前服务端点。"""
        base = self.settings.model_dump()
        mapping = {
            "readers": "n_readers",
            "redundancy": "redundancy",
            "support_threshold": "support_threshold",
            "max_rounds": "max_rounds",
            "visibility": "reader_visibility",
        }
        for source, target in mapping.items():
            if snapshot.get(source) is not None:
                base[target] = snapshot[source]
        if snapshot.get("model"):
            base["llm_model"] = snapshot["model"]
        if snapshot.get("enable_llm_falsifier") is not None:
            base["enable_llm_falsifier"] = bool(snapshot["enable_llm_falsifier"])
        if snapshot.get("adaptive_scheduling") is not None:
            base["adaptive_scheduling"] = bool(snapshot["adaptive_scheduling"])
        for key in (
            "semantic_partitioning",
            "min_independent_support",
            "max_evidence_overlap_rate",
        ):
            if snapshot.get(key) is not None:
                base[key] = snapshot[key]
        return Settings(**base)


def _summary_payload(report, engine) -> dict:
    """结构化结果：给前端画表格与热力图用。"""
    return {
        "run_id": report.run_id,
        "question": report.question,
        "counts": report.counts(),
        "manifest": {
            "plugin": report.manifest.plugin,
            "seed": report.manifest.seed,
            "max_rounds": report.manifest.max_rounds,
            "support_threshold": report.manifest.support_threshold,
            "stop_reason": (
                report.manifest.stop_reason.value if report.manifest.stop_reason else None
            ),
            "total_claims": report.manifest.total_claims,
            "reader_ids": report.manifest.reader_ids,
            "receipts": len(report.manifest.receipts),
            "correlation_budget": report.manifest.correlation_budget,
            "independence": report.independence.model_dump(mode="json"),
            "gap_attribution": report.gap_attribution,
            "gate": report.gate,
            "rounds": [
                {
                    "round": r.round_index,
                    "readers": len(r.assignments),
                    "claims": r.claims_extracted,
                    "new_fingerprints": r.new_fingerprints,
                    "evidence_fill_rate": r.evidence_fill_rate,
                    "coverage_fill_rate": r.coverage_fill_rate,
                    "sparse_cells": r.sparse_cell_count,
                }
                for r in report.manifest.rounds
            ],
        },
        "coverage": {
            "rows": report.coverage.rows,
            "cols": report.coverage.cols,
            "cells": report.coverage.cells,
            "fill_rate": report.coverage.fill_rate(),
        },
        "provenance": {
            "nodes": [node.model_dump(mode="json") for node in report.provenance.nodes],
            "edges": [edge.model_dump(mode="json") for edge in report.provenance.edges],
        },
        "claims": [
            {
                "bucket": bucket,
                "claim_id": c.claim_id,
                "fingerprint": c.fingerprint,
                "statement": c.statement,
                "claim_type": c.claim_type,
                "severity": c.metadata.get("severity"),
                "verified_by": c.verified_by,
                "disputed_with": c.disputed_with,
                "confidence": c.confidence,
                "locator": c.source_refs[0].locator if c.source_refs else None,
                "rationale": c.metadata.get("rationale"),
                "verification_status": c.verification_status,
                "verification_reason": c.metadata.get("verification_reason"),
                "independent_support": c.metadata.get("independent_support", 0),
                "support_components": c.metadata.get("support_components", []),
            }
            for bucket, claims in (
                ("high_confidence", report.high_confidence),
                ("pending", report.pending),
                ("disputed", report.disputed),
            )
            for c in claims
        ],
        "usage": engine.usage_snapshot(),
        "readers_failed": list(engine.runtime.pool.failed_readers),
    }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
