"""每运行的进度事件日志——SSE 的数据源。

## 为什么是「带序号的历史 + 订阅队列」而不是简单的 pub/sub

多智能体审查一轮要跑几十秒到几分钟，期间前端可能刷新、重连、切标签页。
纯 pub/sub 会丢掉断线期间的事件，用户回来只看到一半的时间线。
所以每次运行维护一份**有界事件历史**，每个事件带单调递增的序号；
客户端重连时带上 `Last-Event-ID`，服务端先补发缺口再接着推。

落点是 SSE 而不是 WebSocket：审查任务的进度是**单向**的，不需要双向通道。
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

HISTORY_LIMIT = 2000
"""每次运行保留的事件条数上限。够覆盖一次常见重连，又不至于内存无界。"""


@dataclass(frozen=True)
class Event:
    seq: int
    type: str
    payload: dict
    at: str

    def to_sse(self) -> str:
        """SSE 线格式。

        `event:` 用事件类型而不是固定值，这样前端能按类型挂不同的 handler；
        `id:` 供 `Last-Event-ID` 重放使用。
        """
        data = json.dumps(self.payload, ensure_ascii=False, default=str)
        return f"id: {self.seq}\nevent: {self.type}\ndata: {data}\n\n"


@dataclass
class _Run:
    events: deque[Event] = field(default_factory=lambda: deque(maxlen=HISTORY_LIMIT))
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    closed: bool = False
    seq: int = 0


class RunEventBus:
    """带可选持久化日志的事件总线。

    默认仍是纯内存模式，便于单测和离线运行。服务模式传入 ``journal_dir``
    后，每个运行会额外写入 ``<run_id>/events.jsonl`` 与 ``events.closed``。
    进程重启后 ``history`` 可以从日志恢复，SSE 不会因为实例重启而丢失审计事件。
    日志使用追加写入并在每条事件后 flush + fsync；跨多副本部署时应替换为共享
    数据库或消息日志实现，但上层接口保持不变。
    """

    def __init__(self, journal_dir: Path | str | None = None) -> None:
        self._runs: dict[str, _Run] = {}
        self._journal_dir = Path(journal_dir) if journal_dir else None
        if self._journal_dir:
            self._journal_dir.mkdir(parents=True, exist_ok=True)

    def _journal_path(self, run_id: str) -> Path | None:
        if self._journal_dir is None:
            return None
        return self._journal_dir / run_id / "events.jsonl"

    def _closed_path(self, run_id: str) -> Path | None:
        if self._journal_dir is None:
            return None
        return self._journal_dir / run_id / "events.closed"

    def _append_journal(self, run_id: str, event: Event) -> None:
        path = self._journal_path(run_id)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "seq": event.seq,
                        "type": event.type,
                        "payload": event.payload,
                        "at": event.at,
                    },
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())

    def _load_history(self, run_id: str) -> _Run | None:
        path = self._journal_path(run_id)
        if path is None or not path.exists():
            return None
        run = _Run()
        try:
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    event = Event(
                        seq=int(item["seq"]),
                        type=str(item["type"]),
                        payload=dict(item.get("payload") or {}),
                        at=str(item["at"]),
                    )
                    run.events.append(event)
                    run.seq = max(run.seq, event.seq)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            # 损坏的尾行不能阻止服务查询其他运行；meta.json 仍是状态事实来源。
            return None
        closed = self._closed_path(run_id)
        run.closed = bool(closed and closed.exists())
        self._runs[run_id] = run
        return run

    # ---- 发布 ----

    def publish(self, run_id: str, event_type: str, payload: dict | None = None) -> Event:
        run = self._runs.setdefault(run_id, _Run())
        run.seq += 1
        event = Event(
            seq=run.seq,
            type=event_type,
            payload=payload or {},
            at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        )
        run.events.append(event)
        self._append_journal(run_id, event)
        for queue in list(run.subscribers):
            queue.put_nowait(event)
        return event

    def close(self, run_id: str) -> None:
        """标记运行结束。订阅者会在消费完剩余事件后收到终止信号。"""
        run = self._runs.setdefault(run_id, _Run())
        run.closed = True
        closed = self._closed_path(run_id)
        if closed is not None:
            closed.parent.mkdir(parents=True, exist_ok=True)
            closed.touch()
        for queue in list(run.subscribers):
            # None 作为终止哨兵：订阅者据此退出生成器
            queue.put_nowait(None)
        run.subscribers.clear()

    # ---- 读取 ----

    def history(self, run_id: str, after_seq: int = 0) -> list[Event]:
        run = self._runs.get(run_id) or self._load_history(run_id)
        if run is None:
            return []
        return [e for e in run.events if e.seq > after_seq]

    def is_closed(self, run_id: str) -> bool:
        run = self._runs.get(run_id) or self._load_history(run_id)
        return bool(run and run.closed)

    def subscriber_count(self, run_id: str) -> int:
        run = self._runs.get(run_id)
        return len(run.subscribers) if run else 0

    def forget(self, run_id: str) -> None:
        self._runs.pop(run_id, None)

    # ---- 订阅 ----

    def subscribe(self, run_id: str) -> asyncio.Queue:
        run = self._runs.get(run_id) or self._load_history(run_id) or _Run()
        self._runs[run_id] = run
        queue: asyncio.Queue = asyncio.Queue()
        run.subscribers.append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        run = self._runs.get(run_id)
        if run and queue in run.subscribers:
            run.subscribers.remove(queue)
