"""运行记录与报告的持久化。

磁盘布局（`runs_dir/<run_id>/`）：

    meta.json     运行元信息与状态（列表页只读这一个文件）
    report.md     人类可读报告
    summary.json  结构化结果（结论分桶 + 覆盖率矩阵 + 审计记录）

刻意把 meta 与结果分开：列表页要一次列几十条记录，如果每条都读完整结果会非常慢。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

RunStatus = Literal["queued", "running", "done", "failed"]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class RunRecord(BaseModel):
    """一次审查运行的元信息。"""

    run_id: str
    status: RunStatus = "queued"
    question: str = ""
    repo_path: str = ""
    plugin: str = "code_audit"
    created_at: str = Field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    elapsed_s: float | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    rounds: int = 0
    stop_reason: str | None = None
    llm_calls: int = 0
    readers_failed: int = 0
    settings_snapshot: dict = Field(default_factory=dict)


class RunStore:
    """文件系统实现。

    选文件而不是数据库：一次运行产出一份完整报告，天然是 key-value，
    引入数据库只会增加部署门槛。多实例部署时替换这一个类即可。
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- 路径 ----

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def _meta(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "meta.json"

    # ---- 元信息 ----

    def create(self, record: RunRecord) -> RunRecord:
        self.run_dir(record.run_id).mkdir(parents=True, exist_ok=True)
        self.save_meta(record)
        return record

    def save_meta(self, record: RunRecord) -> None:
        self._meta(record.run_id).write_text(
            json.dumps(record.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, run_id: str) -> RunRecord | None:
        path = self._meta(run_id)
        if not path.exists():
            return None
        try:
            return RunRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("运行记录 %s 无法解析：%s", run_id, exc)
            return None

    def update(self, run_id: str, **fields: object) -> RunRecord | None:
        record = self.get(run_id)
        if record is None:
            return None
        updated = record.model_copy(update=fields)
        self.save_meta(updated)
        return updated

    def list(self, limit: int = 50) -> list[RunRecord]:
        """按创建时间倒序列出。只读 meta.json，不碰结果文件。"""
        records: list[RunRecord] = []
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            record = self.get(child.name)
            if record is not None:
                records.append(record)
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    # ---- 结果 ----

    def save_report(self, run_id: str, markdown: str) -> Path:
        path = self.run_dir(run_id) / "report.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def read_report(self, run_id: str) -> str | None:
        path = self.run_dir(run_id) / "report.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def save_summary(self, run_id: str, payload: dict) -> Path:
        path = self.run_dir(run_id) / "summary.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_summary(self, run_id: str) -> dict | None:
        path = self.run_dir(run_id) / "summary.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
