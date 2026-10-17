"""运行记录与报告的持久化。

磁盘布局（`runs_dir/<run_id>/`）：

    meta.json     运行元信息与状态（列表页只读这一个文件）
    report.md     人类可读报告
    summary.json  结构化结果（结论分桶 + 覆盖率矩阵 + 审计记录）

刻意把 meta 与结果分开：列表页要一次列几十条记录，如果每条都读完整结果会非常慢。
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

RunStatus = Literal["queued", "running", "done", "failed", "canceled"]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    """先写临时文件再原子替换。

    直接 `write_text` 会先清空原文件再写内容，因此在两个动作之间读到的
    是一个**空文件**——而空文件不是"旧内容"，是"解析失败"。
    这个竞态在测试里被真实抓到过：提交后立刻读 `meta.json`，本地 3.13 上碰不到，
    CI 的 3.11/3.12 上稳定复现，表现为 `json.loads("")` 抛 JSONDecodeError。

    生产上同一窗口更糟：进程若在写入中途被杀，留下的是一个永远解析不了的运行记录。
    `os.replace`（`Path.replace`）在同一文件系统内是原子的，因此读者要么看到旧内容、
    要么看到新内容。
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class RunRecord(BaseModel):
    """一次审查运行的元信息。"""

    run_id: str
    status: RunStatus = "queued"
    question: str = ""
    repo_path: str = ""
    repo_url: str | None = None
    commit_sha: str | None = None
    plugin: str = "code_audit"
    created_at: str = Field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    elapsed_s: float | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    rounds: int = 0
    stop_reason: str | None = None
    llm_calls: int = 0
    readers_failed: int = 0
    settings_snapshot: dict = Field(default_factory=dict)
    trace_id: str | None = None
    """网关为本请求分配的 traceId。两端日志靠它对齐同一次请求。"""
    credential_id: str | None = None
    """发起本次运行的 API 凭据。完成回调靠它把用量归到正确的账上。"""


class RunStore:
    """文件系统实现。

    选文件而不是数据库：一次运行产出一份完整报告，天然是 key-value，
    引入数据库只会增加部署门槛。多实例部署时替换这一个类即可。
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- 路径 ----

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def _meta(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "meta.json"

    def _lease(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "worker.lease"

    # ---- 元信息 ----

    def create(self, record: RunRecord) -> RunRecord:
        self.run_dir(record.run_id).mkdir(parents=True, exist_ok=True)
        self.save_meta(record)
        return record

    def save_meta(self, record: RunRecord) -> None:
        _atomic_write(
            self._meta(record.run_id),
            json.dumps(record.model_dump(), ensure_ascii=False, indent=2),
        )

    def get(self, run_id: str) -> RunRecord | None:
        path = self._meta(run_id)
        if not path.exists():
            return None
        try:
            return RunRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("运行记录 %s 无法解析：%s", run_id, exc)
            return None

    def update(self, run_id: str, **fields: object) -> RunRecord | None:
        record = self.get(run_id)
        if record is None:
            return None
        updated = record.model_copy(update=fields)
        self.save_meta(updated)
        return updated

    def claim(self, run_id: str, *, lease_seconds: float = 300.0) -> bool:
        """Atomically claim a queued run for one worker process.

        The service normally runs with one process, but deployments often scale it
        horizontally while sharing the runs volume.  ``O_EXCL`` makes the lease
        creation a cross-process compare-and-set on every supported platform.
        A dead worker leaves a lease behind; its mtime is the heartbeat and an
        expired lease can be reclaimed by the next worker.
        """
        record = self.get(run_id)
        if record is None or record.status not in {"queued", "running"}:
            return False
        lease = self._lease(run_id)
        lease.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        try:
            if lease.exists() and now - lease.stat().st_mtime <= lease_seconds:
                return False
            if lease.exists():
                lease.unlink()
            fd = os.open(str(lease), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(
                    {"pid": os.getpid(), "host": socket.gethostname(), "claimed_at": _now()},
                    stream,
                )
            return True
        except FileExistsError:
            return False
        except OSError as exc:
            logger.warning("无法领取运行 %s：%s", run_id, exc)
            return False

    def release(self, run_id: str) -> None:
        """Release a worker lease; safe to call after a crash or cancellation."""
        try:
            self._lease(run_id).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("无法释放运行 %s 的租约：%s", run_id, exc)

    def lease_active(self, run_id: str, *, lease_seconds: float = 300.0) -> bool:
        lease = self._lease(run_id)
        try:
            return lease.exists() and time.time() - lease.stat().st_mtime <= lease_seconds
        except OSError:
            return False

    def refresh_lease(self, run_id: str) -> None:
        """Heartbeat a lease while a long model run is in progress."""
        try:
            lease = self._lease(run_id)
            if lease.exists():
                os.utime(lease, None)
        except OSError as exc:
            logger.warning("无法刷新运行 %s 的租约：%s", run_id, exc)

    def list(self, limit: int = 50) -> list[RunRecord]:
        """按创建时间倒序列出。只读 meta.json，不碰结果文件。"""
        records: list[RunRecord] = []
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            record = self.get(child.name)
            if record is not None:
                records.append(record)
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    # ---- 结果 ----

    def save_report(self, run_id: str, markdown: str) -> Path:
        path = self.run_dir(run_id) / "report.md"
        _atomic_write(path, markdown)
        return path

    def read_report(self, run_id: str) -> str | None:
        path = self.run_dir(run_id) / "report.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def save_summary(self, run_id: str, payload: dict) -> Path:
        path = self.run_dir(run_id) / "summary.json"
        _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return path

    def read_summary(self, run_id: str) -> dict | None:
        path = self.run_dir(run_id) / "summary.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
