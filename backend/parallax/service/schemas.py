"""HTTP 契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from parallax.service.store import RunRecord


class AuditRequest(BaseModel):
    """提交一次审查。"""

    repo_path: str | None = Field(default=None, description="本地代码仓库路径")
    repo_url: str | None = Field(default=None, description="HTTPS Git 仓库地址")
    commit_sha: str | None = Field(default=None, description="固定审查版本的 Git commit SHA")
    question: str | None = Field(default=None, description="审查目标；留空使用插件默认问题")
    extensions: list[str] | None = Field(default=None, description="要扫描的扩展名，默认 ['.py']")
    group_depth: int | None = Field(default=None, description="模块分组深度")
    max_files: int | None = Field(default=None, description="最多扫描多少个文件")

    # 机制旋钮（不填则用服务默认配置）
    readers: int | None = Field(default=None, ge=1, le=32, description="Reader 数量")
    redundancy: int | None = Field(
        default=None, ge=1, le=32, description="每条证据被几个 Reader 看到（核心实验旋钮）"
    )
    support_threshold: int | None = Field(
        default=None, ge=1, description="判定高置信所需的独立来源数"
    )
    max_rounds: int | None = Field(default=None, ge=1, le=10, description="补检轮次上限")
    visibility: Literal["blind", "shared"] | None = Field(
        default=None, description="blind = 框架正常模式；shared = 传统协作对照组"
    )


class AuditSubmitted(BaseModel):
    run_id: str
    status: str
    events_url: str
    result_url: str


class RunListResponse(BaseModel):
    total: int
    runs: list[RunRecord]


class ComponentInfo(BaseModel):
    name: str
    version: str
    description: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_configured: bool
    model: str = ""


class ReadyResponse(BaseModel):
    ready: bool
    reasons: list[str] = Field(default_factory=list)
