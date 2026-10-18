"""FastAPI 应用。

端点是留给「前端 / Java 网关 / 命令行」三方共用的稳定契约：

    GET  /health                          存活探针
    GET  /ready                           就绪探针（含模型凭据检查）
    GET  /api/v1/meta                     服务能力与当前默认配置
    POST /api/v1/audits                   提交审查 → run_id
    GET  /api/v1/audits                   列出历史运行
    GET  /api/v1/audits/{run_id}          取运行状态与元信息
    GET  /api/v1/audits/{run_id}/events   **SSE 进度流**（支持 Last-Event-ID 重放）
    GET  /api/v1/audits/{run_id}/result   结构化结果（结论 + 覆盖率矩阵 + 审计）
    GET  /api/v1/audits/{run_id}/report   Markdown 报告
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from parallax import __version__
from parallax.config import Settings, load_settings
from parallax.domain.errors import ConfigurationError
from parallax.plugins.code_audit import DEFECT_CLASSES
from parallax.service.events import RunEventBus
from parallax.service.runner import AuditRunner
from parallax.service.schemas import (
    AuditRequest,
    AuditSubmitted,
    HealthResponse,
    ReadyResponse,
    RunListResponse,
)
from parallax.service.store import RunStore
from parallax.service.trace import (
    CREDENTIAL_HEADER,
    TRACE_HEADER,
    install_log_filter,
    set_trace_id,
)

logger = logging.getLogger(__name__)

SSE_KEEPALIVE_SECONDS = 15.0
"""SSE 心跳间隔。

反向代理（nginx 默认 60s）会掐掉长时间无数据的连接。定期发注释行既保活，
也让浏览器知道连接仍然健康。
"""


def create_app(
    settings: Settings | None = None,
    *,
    runs_dir: Path | str | None = None,
    client_factory=None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """构建应用。

    把 settings / runs_dir / client_factory 都做成参数，是为了让测试能注入
    临时目录与假模型客户端——不需要网络、不烧 API 额度、不污染真实运行记录。
    """
    resolved = settings or load_settings()
    store = RunStore(Path(runs_dir) if runs_dir else resolved.runs_dir)
    # 事件日志与运行产物放在同一目录：重启后 SSE 可以从磁盘恢复历史。
    bus = RunEventBus(store.root)
    runner = AuditRunner(store, bus, resolved, client_factory=client_factory)
    install_log_filter(logging.getLogger("parallax"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Parallax 服务启动：runs_dir=%s model=%s", store.root, resolved.llm_model)
        recovered = runner.recover()
        if recovered:
            logger.info("已恢复 %d 个未完成审查任务", recovered)
        yield
        logger.info("Parallax 服务停止：等待在跑任务收敛")
        await runner.shutdown()

    app = FastAPI(
        title="Parallax",
        description="抗从众的多智能体证据装配框架",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.store = store
    app.state.bus = bus
    app.state.runner = runner

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 探针 ----

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            llm_configured=resolved.is_llm_configured(),
            model=resolved.llm_model,
        )

    @app.get("/ready", response_model=ReadyResponse)
    async def ready() -> ReadyResponse:
        """就绪探针。

        把一个"服务活着但没法干活"的状态显式暴露出来：
        容器编排据此不把流量导入未配置模型凭据的实例。
        """
        reasons: list[str] = []
        if not resolved.is_llm_configured():
            reasons.append("未配置 PARALLAX_LLM_API_KEY")
        if not store.root.exists():
            reasons.append(f"runs 目录不可用：{store.root}")
        return ReadyResponse(ready=not reasons, reasons=reasons)

    @app.get("/api/v1/meta")
    async def meta() -> dict:
        return {
            "version": __version__,
            "defaults": {
                "readers": resolved.n_readers,
                "redundancy": resolved.redundancy,
                "support_threshold": resolved.support_threshold,
                "max_rounds": resolved.max_rounds,
                "visibility": resolved.reader_visibility,
                "model": resolved.llm_model,
                "max_evidence_per_call": resolved.max_evidence_per_call,
                "adaptive_scheduling": resolved.adaptive_scheduling,
                "enable_llm_falsifier": resolved.enable_llm_falsifier,
            },
            "plugins": [
                {
                    "name": "code_audit",
                    "description": "AI 生成代码的独立审查",
                    "defect_classes": list(DEFECT_CLASSES),
                }
            ],
        }

    # ---- 提交与查询 ----

    @app.post("/api/v1/audits", response_model=AuditSubmitted, status_code=202)
    async def submit_audit(
        request: AuditRequest,
        x_trace_id: str | None = Header(default=None, alias=TRACE_HEADER),
        x_credential_id: str | None = Header(default=None, alias=CREDENTIAL_HEADER),
    ) -> AuditSubmitted:
        # 把 traceId 放进上下文：本请求的日志与随后派生的后台任务都会带上它。
        # asyncio.create_task 会复制当前上下文，因此运行期间的日志也能对上。
        set_trace_id(x_trace_id)
        try:
            record = runner.submit(
                repo_path=request.repo_path,
                overrides=request.model_dump(exclude_none=True),
                trace_id=x_trace_id,
                credential_id=x_credential_id,
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.info(
            "已接受提交 run_id=%s repo=%s credential=%s",
            record.run_id,
            record.repo_path,
            x_credential_id or "-",
        )
        return AuditSubmitted(
            run_id=record.run_id,
            status=record.status,
            events_url=f"/api/v1/audits/{record.run_id}/events",
            result_url=f"/api/v1/audits/{record.run_id}/result",
        )

    @app.post("/api/v1/webhooks/github", status_code=202)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_event: str | None = Header(default=None),
        x_trace_id: str | None = Header(default=None, alias=TRACE_HEADER),
    ) -> dict:
        """接受签名 GitHub PR 事件，并固定审查 head commit。"""
        if not resolved.webhook_secret:
            raise HTTPException(status_code=404, detail="GitHub webhook 未启用")
        body = await request.body()
        expected = (
            "sha256=" + hmac.new(resolved.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="webhook 签名无效")
        if x_github_event not in {"opened", "reopened", "synchronize"}:
            return {"accepted": False, "reason": "事件类型不触发审查"}
        try:
            payload = json.loads(body)
            repo_url = payload["repository"]["clone_url"]
            commit_sha = payload["pull_request"]["head"]["sha"]
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail="webhook 缺少 repository/PR head 信息"
            ) from exc
        set_trace_id(x_trace_id)
        try:
            record = runner.submit(
                repo_path=None,
                overrides={
                    "repo_url": repo_url,
                    "commit_sha": commit_sha,
                    "question": "审查这个 Pull Request 中真实存在的缺陷，并说明触发条件。",
                },
                trace_id=x_trace_id,
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "accepted": True,
            "run_id": record.run_id,
            "status": record.status,
            "commit_sha": record.commit_sha,
            "events_url": f"/api/v1/audits/{record.run_id}/events",
        }

    @app.get("/api/v1/audits", response_model=RunListResponse)
    async def list_audits(limit: int = Query(default=50, ge=1, le=200)) -> RunListResponse:
        runs = store.list(limit=limit)
        return RunListResponse(total=len(runs), runs=runs)

    @app.get("/api/v1/audits/{run_id}")
    async def get_audit(run_id: str) -> dict:
        record = store.get(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"未找到运行 {run_id}")
        return record.model_dump()

    @app.delete("/api/v1/audits/{run_id}")
    async def cancel_audit(run_id: str) -> dict:
        record = runner.cancel(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"未找到运行 {run_id}")
        return record.model_dump()

    @app.get("/api/v1/audits/{run_id}/result")
    async def get_result(run_id: str) -> dict:
        record = store.get(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"未找到运行 {run_id}")
        summary = store.read_summary(run_id)
        if summary is None:
            # 结果还没产出不算错误——前端应当继续看事件流，而不是当成失败
            return {"run_id": run_id, "status": record.status, "ready": False}
        return {"run_id": run_id, "status": record.status, "ready": True, "result": summary}

    @app.get("/api/v1/audits/{run_id}/report", response_class=PlainTextResponse)
    async def get_report(run_id: str) -> str:
        report = store.read_report(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="报告尚未生成")
        return report

    # ---- SSE ----

    @app.get("/api/v1/audits/{run_id}/events")
    async def stream_events(
        run_id: str,
        request: Request,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        after: int = Query(default=0, ge=0, description="从该序号之后开始推（本地调试用）"),
    ) -> StreamingResponse:
        if store.get(run_id) is None:
            raise HTTPException(status_code=404, detail=f"未找到运行 {run_id}")

        # 断线重连时按 Last-Event-ID 补发缺口；首次连接从头开始。
        # ⚠️ 起点的计算必须在生成器**外面**做：生成器内部会对游标重新赋值，
        # 那样它就成了生成器的局部变量，读取时必然 UnboundLocalError。
        start_seq = after
        if last_event_id:
            # Last-Event-ID 是客户端给的，格式不对就忽略，绝不能因此中断流式
            with contextlib.suppress(ValueError):
                start_seq = max(start_seq, int(last_event_id))

        async def generator():
            position = start_seq
            queue = bus.subscribe(run_id)
            try:
                # ① 先补历史（含本次连接建立前已经发生的事件）
                for event in bus.history(run_id, position):
                    position = event.seq
                    yield event.to_sse()
                if bus.is_closed(run_id):
                    return

                # ② 再实时推送
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_SECONDS)
                    except TimeoutError:
                        # 心跳注释行：既保活，也不会被 EventSource 当作数据事件
                        yield ": keepalive\n\n"
                        continue
                    if event is None:  # 终止哨兵
                        return
                    position = event.seq
                    yield event.to_sse()
            finally:
                bus.unsubscribe(run_id, queue)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                # 关掉 nginx 缓冲，否则 SSE 会被攒起来一起发，流式就失去意义
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = None  # uvicorn 目标由 factory 提供，见 `parallax.service.app:create_app --factory`


def main() -> None:  # pragma: no cover - 便捷启动入口
    import os

    import uvicorn

    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=os.environ.get("PARALLAX_HOST", "0.0.0.0"),
        port=int(os.environ.get("PARALLAX_PORT", "8000")),
        log_level=os.environ.get("PARALLAX_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
