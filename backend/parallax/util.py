"""通用小工具：确定性 ID 与哈希。

为什么不用 uuid4：本框架对外承诺「可复现」。同一份输入必须产出同一套 ID，
否则 run manifest 无法用于审计复盘，实验对照组也无法对齐。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_SEP = "\x1f"


def stable_id(*parts: Any, prefix: str = "", length: int = 12) -> str:
    """由输入内容派生的确定性 ID（sha1 前 N 位十六进制）。"""
    payload = _SEP.join(
        json.dumps(p, sort_keys=True, ensure_ascii=False, default=str)
        if not isinstance(p, str)
        else p
        for p in parts
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}{digest}" if prefix else digest


def content_hash(text: str) -> str:
    """证据正文的规范化哈希，用于去重与漂移比对。"""
    normalized = " ".join(text.split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def cell_key(row: str, col: str) -> str:
    """覆盖率矩阵的单元格键。

    Pydantic 对 tuple 键的 JSON 序列化不友好，所以统一用不可见分隔符拼字符串。
    """
    return f"{row}{_SEP}{col}"


def split_cell_key(key: str) -> tuple[str, str]:
    row, _, col = key.partition(_SEP)
    return row, col
