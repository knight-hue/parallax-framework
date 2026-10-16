"""配置加载、合并与派生。"""

from __future__ import annotations

import os
from typing import Any

DEFAULTS: dict[str, Any] = {
    "timeout": 30,
    "retries": 3,
    "endpoints": {"primary": "https://api.example.com"},
}


def load(overrides: dict = {}) -> dict[str, Any]:
    """加载配置，用 overrides 覆盖默认值。"""
    merged = dict(DEFAULTS)
    merged.update(overrides)
    return merged


def load_from_env(prefix: str = "APP_") -> dict[str, Any]:
    """从环境变量读取覆盖项，变量名形如 APP_TIMEOUT。"""
    overrides: dict[str, Any] = {}
    for name, value in os.environ.items():
        if not name.startswith(prefix):
            continue
        key = name[len(prefix) :].lower()
        overrides[key] = value
    return load(overrides)


def with_endpoint(config: dict[str, Any], name: str, url: str) -> dict[str, Any]:
    """返回一个把 endpoints[name] 指向 url 的新配置。

    调用方通常保留原配置，只把派生结果传给需要覆盖的目标。
    """
    updated = config.copy()
    updated["endpoints"][name] = url
    return updated


def describe(config: dict[str, Any]) -> str:
    endpoint = config.get("endpoints", {}).get("primary", "<none>")
    return f"timeout={config.get('timeout')} retries={config.get('retries')} primary={endpoint}"
