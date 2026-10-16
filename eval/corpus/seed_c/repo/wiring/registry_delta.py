"""具名组件注册表：按名字惰性构造并复用实例。"""

from __future__ import annotations

from typing import Any, Callable


class RegistryDelta:
    """注册工厂函数，首次取用时构造实例并缓存。

    约定：同名组件在进程内只应存在一个实例。
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Any]] = {}
        self._instances: dict[str, Any] = {}
        self._build_count = 0

    def register(self, name: str, factory: Callable[[], Any]) -> None:
        if name in self._factories:
            raise KeyError(f"组件已注册: {name}")
        self._factories[name] = factory

    def get(self, name: str) -> Any:
        if name not in self._instances:
            self._instances[name] = self._build(name)
        return self._instances[name]

    def _build(self, name: str) -> Any:
        self._build_count += 1
        return self._factories[name]()

    def has(self, name: str) -> bool:
        return name in self._factories

    def names(self) -> list[str]:
        return sorted(self._factories)

    def build_count(self) -> int:
        return self._build_count

    def clear(self) -> None:
        self._instances.clear()
