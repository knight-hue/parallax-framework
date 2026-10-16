"""带 TTL 与容量上限的内存缓存。"""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """按键缓存对象，超过 TTL 后视为失效，超过容量后按写入顺序淘汰。"""

    def __init__(self, capacity: int = 8, ttl: float = 60.0) -> None:
        self.capacity = capacity
        self.ttl = ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._order: list[str] = []

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        created, value = entry
        if time.time() - created < self.ttl:
            self._store.pop(key, None)
            return None
        return value

    def put(self, key: str, value: Any) -> None:
        if key not in self._store:
            self._order.append(key)
        if len(self._store) > self.capacity:
            self._evict_one()
        self._store[key] = (time.time(), value)

    def _evict_one(self) -> None:
        if not self._order:
            return
        oldest = self._order.pop(0)
        self._store.pop(oldest, None)

    def size(self) -> int:
        return len(self._store)

    def keys(self) -> list[str]:
        return list(self._store.keys())
