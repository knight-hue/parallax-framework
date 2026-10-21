"""Platform worker lifecycle: Java is authoritative, local journal is a spool."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from weakref import WeakValueDictionary

from parallax.config import Settings
from parallax.engine import ParallaxEngine
from parallax.infra.llm_openai_compat import OpenAICompatClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from parallax.service.platform_client import PlatformClient, PlatformRejected, PlatformUnavailable
from parallax.service.platform_sources import PlatformSources
from parallax.service.worker_journal import JournalConflict, WorkerJournal
from parallax.service.worker_protocol import WorkerTask

logger = logging.getLogger(__name__)


class _PlatformCanceled(Exception):
    """Cancellation observed in an authoritative platform acknowledgement."""


class PlatformWorkerService:
    """Executes one Java task after a durable STARTED grant.

    The engine factory is injected so tests and deployments can choose the normal
    Parallax engine. No model/source work starts before the grant is acknowledged.
    """

    def __init__(
        self,
        settings: Settings,
        root: Path,
        *,
        client_factory: Callable[[Settings], PlatformClient] | None = None,
        engine_factory: Callable[..., Awaitable[tuple[object, int, int, str]]] | None = None,
    ):
        if not settings.gateway_internal_token:
            raise ValueError("Platform worker requires a gateway internal token")
        if not settings.platform_url:
            raise ValueError("Platform worker requires a fixed platform URL")
        hosts = set(settings.platform_source_hosts)
        self.settings = settings
        self.root = Path(root)
        self.journal = WorkerJournal(self.root / "worker-journal.sqlite3")
        self.client_factory = client_factory or (
            lambda current: PlatformClient(current.platform_url, current.gateway_internal_token)
        )
        self.engine_factory = engine_factory or self.execute_default
        self.sources = PlatformSources(self.root / "sources", hosts)
        self._running: dict[tuple[str, int], asyncio.Task] = {}
        self._delivery_locks: WeakValueDictionary[tuple[str, int], asyncio.Lock] = (
            WeakValueDictionary()
        )
        self._replayer: asyncio.Task | None = None
        self._closing = False

    async def start(self):
        if self._closing:
            raise PlatformUnavailable("Platform worker is shutting down")
        if self._replayer is None:
            self._replayer = asyncio.create_task(self._replay_loop())

    def _delivery_lock(self, task_id, attempt):
        key = (task_id, attempt)
        lock = self._delivery_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._delivery_locks[key] = lock
        return lock

    async def shutdown(self):
        self._closing = True
        if self._replayer is not None:
            self._replayer.cancel()
            await asyncio.gather(self._replayer, return_exceptions=True)
            self._replayer = None
        running = list(self._running.values())
        for work in running:
            work.cancel()
        await asyncio.gather(*running, return_exceptions=True)

    async def _replay_loop(self):
        while True:
            try:
                await self.replay()
            except Exception:  # noqa: BLE001
                logger.exception("Platform receipt replay failed")
            await asyncio.sleep(self.settings.platform_replay_seconds)

    async def execute_default(self, *, task, snapshot, sources, canceled):
        """Run the existing evidence engine under the immutable Java policy."""
        policy = snapshot.policy()
        if canceled() or datetime.now(UTC) >= task.deadline:
            raise asyncio.CancelledError
        settings = self.settings.model_copy(
            update={
                "n_readers": policy.readers,
                "redundancy": policy.redundancy,
                "max_rounds": policy.maxRounds,
                "support_threshold": policy.minIndependentSupport,
                "max_tokens": task.token_budget,
                "enable_llm_falsifier": policy.falsifierEnabled,
                "audit_root": "",
            }
        )
        source = await asyncio.to_thread(sources.resolve, snapshot.clone_url, task.commit_sha)
        client = OpenAICompatClient(settings)
        try:
            engine = ParallaxEngine.build(
                adapter=RepoAdapter(
                    source.path, extensions=(".py", ".java", ".js", ".ts"), max_files=300
                ),
                plugin=CodeAuditReader(),
                client=client,
                settings=settings,
            )
            report = await engine.run(
                "找出这个提交源码中真实存在的缺陷，并说明触发条件。",
                run_id=task.task_id,
            )
            if canceled():
                raise asyncio.CancelledError
            payload = report.model_dump(mode="json")
            digest = hashlib.sha256(
                json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            usage = engine.usage_snapshot()
            content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return content, usage["prompt_tokens"], usage["completion_tokens"], digest
        finally:
            await client.aclose()

    async def dispatch(self, task: WorkerTask) -> str:
        """Register and claim once; duplicate delivery is acknowledged safely."""
        if self._closing:
            raise PlatformUnavailable("Platform worker is shutting down")
        self.journal.register(task)
        if not self.journal.claim_launch(task):
            return "duplicate"
        client = self.client_factory(self.settings)
        handed_off = False
        try:
            snapshot = await client.snapshot(task)
            async with self._delivery_lock(task.task_id, task.attempt):
                started = self.journal.prepare(task, "STARTED", 0, 0)
                acknowledgement = await client.send(started)
                self.journal.acknowledge(started)
            if self._closing:
                raise PlatformUnavailable("Platform worker is shutting down")
            if (
                snapshot.cancel_requested
                or acknowledgement.get("cancelRequested", False)
                or self.journal.canceled(task)
            ):
                await self._finish(client, task, "CANCELED", 0, 0)
                return "canceled"
            if self.engine_factory is None:
                raise RuntimeError("Platform engine factory is not configured")
            work = asyncio.create_task(self._execute(client, task, snapshot))
            self._running[(task.task_id, task.attempt)] = work
            work.add_done_callback(lambda _: self._running.pop((task.task_id, task.attempt), None))
            handed_off = True
            return "started"
        finally:
            if not handed_off:
                await client.aclose()

    async def cancel(self, task: WorkerTask) -> str:
        self.journal.request_cancel(task)
        running = self._running.get((task.task_id, task.attempt))
        if running is not None:
            running.cancel()
        return "accepted"

    async def _execute(self, client: PlatformClient, task: WorkerTask, snapshot) -> None:
        prompt = completion = 0
        engine = heartbeat = None
        stop_heartbeat = asyncio.Event()
        try:
            remaining = (task.deadline - datetime.now(UTC)).total_seconds()
            async with asyncio.timeout(max(0, remaining)):
                engine = asyncio.create_task(
                    self.engine_factory(
                        task=task,
                        snapshot=snapshot,
                        sources=self.sources,
                        canceled=lambda: self.journal.canceled(task),
                    )
                )
                heartbeat = asyncio.create_task(self._heartbeat(client, task, stop_heartbeat))
                done, _ = await asyncio.wait(
                    {engine, heartbeat}, return_when=asyncio.FIRST_COMPLETED
                )
                if heartbeat in done:
                    await heartbeat
                content, prompt, completion, digest = await engine
                stop_heartbeat.set()
                await heartbeat
                await client.upload_artifact(task, uuid4().hex, digest, content)
                await self._finish(client, task, "SUCCEEDED", prompt, completion, digest)
        except _PlatformCanceled:
            self.journal.request_cancel(task)
            logger.warning(
                "Stopping canceled platform task %s with uncertain in-flight usage", task.task_id
            )
        except asyncio.CancelledError:
            # Shutdown/cancellation cannot prove an in-flight provider call spent
            # nothing. Let Java expire the lease and conservatively settle it.
            logger.info(
                "Platform task %s interrupted; awaiting authoritative recovery", task.task_id
            )
        except (TimeoutError, PlatformUnavailable):
            # Do not invent zero-cost completion while provider work may have spent.
            # Keep exact pending receipts; Java recovery settles uncertain usage.
            logger.warning("Stopping platform task %s after deadline or lost contact", task.task_id)
        except (PlatformRejected, JournalConflict):
            logger.info("Platform task %s became stale", task.task_id)
        except Exception:  # noqa: BLE001
            logger.exception("Platform task %s failed", task.task_id)
        finally:
            for work in (engine, heartbeat):
                if work is not None:
                    work.cancel()
            await asyncio.gather(
                *(work for work in (engine, heartbeat) if work is not None), return_exceptions=True
            )
            await client.aclose()

    async def _heartbeat(self, client, task, stop):
        while True:
            try:
                await asyncio.wait_for(stop.wait(), self.settings.platform_heartbeat_seconds)
                return
            except TimeoutError:
                pass
            async with self._delivery_lock(task.task_id, task.attempt):
                if stop.is_set():
                    return
                event = self.journal.prepare(task, "PROGRESS", 0, 0)
                acknowledgement = await client.send(event)
                self.journal.acknowledge(event)
            if acknowledgement.get("cancelRequested", False):
                raise _PlatformCanceled

    async def _finish(self, client, task, kind, prompt, completion, digest=None):
        async with self._delivery_lock(task.task_id, task.attempt):
            event = self.journal.prepare(task, kind, prompt, completion, digest)
            try:
                await client.send(event)
                self.journal.acknowledge(event)
            except PlatformUnavailable:
                logger.warning("Retaining unacknowledged %s event for replay", event.event_id)

    async def replay(self, limit: int = 100) -> int:
        """Retry exact persisted receipts; never invent a new event or launch."""
        sent = 0
        for event in self.journal.pending(limit):
            lock = self._delivery_lock(event.task_id, event.attempt)
            # A slow unrelated delivery must not delay a live task's heartbeat.
            if lock.locked() or (event.task_id, event.attempt) in self._running:
                continue
            async with lock:
                if not self.journal.is_pending(event):
                    continue
                client = self.client_factory(self.settings)
                try:
                    await client.send(event)
                    self.journal.acknowledge(event)
                    sent += 1
                except (PlatformUnavailable, PlatformRejected):
                    continue
                finally:
                    await client.aclose()
        return sent
