"""定长资源池：借出、归还、超时等待。"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class PoolAlpha:
    """定长资源池。

    acquire() 借出一个资源（必要时新建或等待）；release() 归还。
    池内资源总数不超过 size。
    """

    def __init__(self, factory: Callable[[], Any], size: int = 32) -> None:
        self._factory = factory
        self._size = size
        self._free: list[Any] = []
        self._in_use: set[int] = set()
        self._created = 0
        self._lock = threading.Lock()
        self._available = threading.Condition(self._lock)

    def acquire(self, timeout: float = 5.0) -> Any:
        deadline = time.monotonic() + timeout
        with self._available:
            while True:
                if self._free:
                    resource = self._free.pop()
                    self._in_use.add(id(resource))
                    return resource
                if self._created < self._size:
                    resource = self._factory()
                    self._created += 1
                    self._in_use.add(id(resource))
                    return resource
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("资源池已耗尽")
                self._available.wait(remaining)

    def release(self, resource: Any) -> None:
        with self._available:
            self._free.append(resource)
            self._available.notify()

    def stats(self) -> dict[str, int]:
        return {
            "created": self._created,
            "free": len(self._free),
            "in_use": len(self._in_use),
        }

    def close(self) -> None:
        with self._available:
            closer = getattr(self._factory, "close", None)
            for resource in self._free:
                if callable(closer):
                    closer(resource)
            self._free.clear()
