"""追加式记录日志：写入、重放、按保留量压缩。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JournalTheta:
    """以 JSON Lines 落盘的记录日志。

    append() 追加一条并重写文件；
    compact() 只保留最近 keep 条；
    replay() 按写入顺序返回当前全部记录。
    """

    def __init__(self, path: str | Path, keep: int = 200) -> None:
        self.path = Path(path)
        self.keep = keep
        self._records: list[dict[str, Any]] = []
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                self._records.append(json.loads(line))

    def _serialise(self, records: list[dict[str, Any]]) -> str:
        return "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        )

    def _flush(self) -> None:
        self.path.write_text(self._serialise(self._records), encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        self._records.append(record)
        self._flush()

    def compact(self) -> int:
        """只保留最近 keep 条记录，返回被丢弃的条数。"""
        surplus = len(self._records) - self.keep
        if surplus <= 0:
            return 0
        kept = self._records[surplus:]
        self.path.write_text(self._serialise(kept), encoding="utf-8")
        return surplus

    def replay(self) -> list[dict[str, Any]]:
        return list(self._records)

    def count(self) -> int:
        return len(self._records)

    def disk_count(self) -> int:
        return sum(
            1
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
