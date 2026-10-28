"""Prometheus 文本导出（不依赖 prometheus_client）。

## 为什么手写而不是引入客户端库

1. 本机离线环境没有 `prometheus_client`，为一条导出端点引入新依赖不划算；
2. 文本格式本身极简单（`# HELP` / `# TYPE` / `name{label="v"} value`）；
3. 手写可以保证**只导出真实存在的指标**——不写空壳指标，避免抓到一条永远为 0 的假信号。

## 已知边界

这里只有服务自身的低基数指标（运行数、租约数、构建信息），
没有进程级 CPU/内存，也没有直方图。需要更细的指标时再引入客户端库，
而不是在这里堆一个不完整的自定义实现。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

KNOWN_STATUSES = ("queued", "running", "done", "failed", "canceled")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus(
    statuses: Sequence[str],
    *,
    version: str,
    active_leases: int = 0,
) -> str:
    """把运行状态列表渲染成 Prometheus 文本格式。"""
    counts = Counter(statuses)
    ordered = list(KNOWN_STATUSES) + sorted(set(counts) - set(KNOWN_STATUSES))

    lines: list[str] = [
        "# HELP parallax_up 服务进程可被抓取（恒为 1）",
        "# TYPE parallax_up gauge",
        "parallax_up 1",
        "# HELP parallax_build_info 构建信息，值恒为 1",
        "# TYPE parallax_build_info gauge",
        f'parallax_build_info{{version="{_escape(version)}"}} 1',
        "# HELP parallax_runs 运行记录数，按状态分组",
        "# TYPE parallax_runs gauge",
    ]
    for status in ordered:
        lines.append(f'parallax_runs{{status="{_escape(status)}"}} {counts.get(status, 0)}')
    lines.extend(
        [
            "# HELP parallax_runs_total 运行记录总数",
            "# TYPE parallax_runs_total gauge",
            f"parallax_runs_total {len(statuses)}",
            "# HELP parallax_active_leases 当前持有未过期租约的运行数",
            "# TYPE parallax_active_leases gauge",
            f"parallax_active_leases {active_leases}",
        ]
    )
    return "\n".join(lines) + "\n"
