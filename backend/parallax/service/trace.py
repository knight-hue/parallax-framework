"""链路追踪上下文。

网关给每个请求分配 `X-Trace-Id`，本服务要把它**贯穿到整条运行**：
请求内写进日志，运行结束后写进 `meta.json` 与完成回调。
没有它，"这次运行的 183 次模型调用"和"网关那边的 429"就只能靠时间戳猜关系。

用 `ContextVar` 而不是线程局部变量：本服务是 asyncio 单线程多任务，
线程局部变量会让并发运行的多个任务互相覆盖 traceId。

`asyncio.create_task` 会**复制**当前上下文，所以提交请求时设下的 traceId
会被后台运行任务继承，而不同运行的上下文互不影响。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

TRACE_HEADER = "X-Trace-Id"
CREDENTIAL_HEADER = "X-Parallax-Credential-Id"

_current_trace_id: ContextVar[str | None] = ContextVar("parallax_trace_id", default=None)


def set_trace_id(trace_id: str | None) -> None:
    _current_trace_id.set(trace_id or None)


def current_trace_id() -> str | None:
    return _current_trace_id.get()


class TraceLogFilter(logging.Filter):
    """把 traceId 注入每条日志记录。

    装到 logger 上而不是格式化字符串里做魔法查找：格式化字符串里
    取一个不存在的字段会直接抛异常，把一次日志变成一次故障。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = current_trace_id() or "-"
        return True


def install_log_filter(logger: logging.Logger | None = None) -> None:
    """给 logger 及其 handler 装上过滤器（已装过则跳过）。"""
    target = logger or logging.getLogger("parallax")
    if not any(isinstance(f, TraceLogFilter) for f in target.filters):
        target.addFilter(TraceLogFilter())
    for handler in target.handlers:
        if not any(isinstance(f, TraceLogFilter) for f in handler.filters):
            handler.addFilter(TraceLogFilter())
