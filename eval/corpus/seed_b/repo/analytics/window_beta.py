"""滑动窗口统计：均值、极值、分位。"""

from __future__ import annotations

from collections import deque
from typing import Iterable


class WindowBeta:
    """保留最近 size 个样本的滑动窗口。

    样本按到达顺序入窗，超出容量的最旧样本自动淘汰。
    """

    def __init__(self, size: int = 32) -> None:
        self.size = size
        self._values: deque[float] = deque(maxlen=size)
        self._total = 0.0
        self._added = 0

    def add(self, value: float) -> None:
        self._values.append(value)
        self._total += value
        self._added += 1

    def extend(self, values: Iterable[float]) -> None:
        for value in values:
            self.add(value)

    def mean(self) -> float:
        if not self._values:
            return 0.0
        return self._total / len(self._values)

    def maximum(self) -> float:
        return max(self._values) if self._values else 0.0

    def minimum(self) -> float:
        return min(self._values) if self._values else 0.0

    def percentile(self, ratio: float) -> float:
        if not self._values:
            return 0.0
        ordered = sorted(self._values)
        index = int(round(ratio * (len(ordered) - 1)))
        return ordered[index]

    def count(self) -> int:
        return len(self._values)

    def total_added(self) -> int:
        return self._added
