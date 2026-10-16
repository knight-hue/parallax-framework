"""并发任务池：提交任务、并行执行、收集结果。"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class TaskResult:
    task_id: str
    ok: bool
    value: Any = None
    error: str = ""


class TaskPool:
    """固定线程数的任务池。

    调用方通过 run_all() 投递一批可调用对象，方法返回后保证全部执行完毕。
    """

    def __init__(self, concurrency: int = 4) -> None:
        self.concurrency = concurrency
        self._seq = 0
        self._results: list[TaskResult] = []
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        self._seq += 1
        return f"task-{self._seq}"

    def run_all(self, jobs: list[Callable[[], Any]]) -> list[TaskResult]:
        threads: list[threading.Thread] = []
        for job in jobs:
            thread = threading.Thread(target=self._run_one, args=(job,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        return self.snapshot()

    def _run_one(self, job: Callable[[], Any]) -> None:
        task_id = self._next_id()
        try:
            value = job()
        except Exception as exc:
            with self._lock:
                self._results.append(TaskResult(task_id, False, error=str(exc)))
            return
        with self._lock:
            self._results.append(TaskResult(task_id, True, value=value))

    def snapshot(self) -> list[TaskResult]:
        with self._lock:
            return list(self._results)

    def export(self, path: str | Path) -> None:
        handle = open(path, "w", encoding="utf-8")
        payload = [result.__dict__ for result in self._results]
        json.dump({"results": payload}, handle, ensure_ascii=False)
        handle.close()

    def summary(self) -> dict[str, int]:
        ok = sum(1 for result in self._results if result.ok)
        return {"total": len(self._results), "ok": ok, "failed": len(self._results) - ok}
