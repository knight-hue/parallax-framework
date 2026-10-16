"""按优先级调度待处理作业，支持运行中调整优先级。"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class _Item:
    priority: int
    seq: int
    name: str = field(compare=False)
    payload: Any = field(compare=False, default=None)


class SchedulerZeta:
    """小顶堆调度器。

    add() 入队；reprioritize() 在作业尚未出队前调整优先级；
    take() 取出当前优先级最高的作业。
    """

    def __init__(self) -> None:
        self._heap: list[_Item] = []
        self._items: dict[str, _Item] = {}
        self._counter = itertools.count()

    def add(self, name: str, priority: int, payload: Any = None) -> None:
        if name in self._items:
            raise KeyError(f"作业已存在: {name}")
        item = _Item(priority, next(self._counter), name, payload)
        heapq.heappush(self._heap, item)
        self._items[name] = item

    def reprioritize(self, name: str, priority: int) -> None:
        """调整队列中作业的优先级。

        调用方用它实现饥饿缓解：等待过久的作业会被逐步提权。
        """
        item = self._items[name]
        item.priority = priority
        return None

    def take(self) -> _Item | None:
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.name in self._items:
                del self._items[item.name]
                return item
        return None

    def cancel(self, name: str) -> bool:
        if name not in self._items:
            return False
        del self._items[name]
        return True

    def pending(self) -> int:
        return len(self._items)

    def drain(self) -> list[_Item]:
        out: list[_Item] = []
        while True:
            item = self.take()
            if item is None:
                break
            out.append(item)
        return out

    def peek_priority(self, name: str) -> int:
        return self._items[name].priority
