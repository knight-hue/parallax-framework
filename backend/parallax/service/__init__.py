"""HTTP 服务层：把框架暴露成可部署、可流式观测的服务。

events.py   每运行的进度事件日志（SSE 的数据源，支持断线重放）
store.py    运行记录与报告的持久化
runner.py   后台执行的编排（提交即返回，进度走事件流）
schemas.py  HTTP 契约
app.py      FastAPI 应用
"""

from parallax.service.events import Event, RunEventBus
from parallax.service.runner import AuditRunner
from parallax.service.store import RunRecord, RunStore

__all__ = ["AuditRunner", "Event", "RunEventBus", "RunRecord", "RunStore"]
