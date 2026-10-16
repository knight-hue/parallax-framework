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
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

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
    """进程内事件总线。

    刻意不做跨进程：审查任务本身就是单进程后台任务，
    引入 Redis Pub/Sub 只会增加部署负担而不增加能力。
    将来要多副本时替换这一个类即可（接口只有 publish / history / subscribe）。
    """

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}

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
        for queue in list(run.subscribers):
            queue.put_nowait(event)
        return event

    def close(self, run_id: str) -> None:
        """标记运行结束。订阅者会在消费完剩余事件后收到终止信号。"""
        run = self._runs.setdefault(run_id, _Run())
        run.closed = True
        for queue in list(run.subscribers):
            # None 作为终止哨兵：订阅者据此退出生成器
            queue.put_nowait(None)
        run.subscribers.clear()

    # ---- 读取 ----

    def history(self, run_id: str, after_seq: int = 0) -> list[Event]:
        run = self._runs.get(run_id)
        if run is None:
            return []
        return [e for e in run.events if e.seq > after_seq]

    def is_closed(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        return bool(run and run.closed)

    def subscriber_count(self, run_id: str) -> int:
        run = self._runs.get(run_id)
        return len(run.subscribers) if run else 0

    def forget(self, run_id: str) -> None:
        self._runs.pop(run_id, None)

    # ---- 订阅 ----

    def subscribe(self, run_id: str) -> asyncio.Queue:
        run = self._runs.setdefault(run_id, _Run())
        queue: asyncio.Queue = asyncio.Queue()
        run.subscribers.append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        run = self._runs.get(run_id)
        if run and queue in run.subscribers:
            run.subscribers.remove(queue)
