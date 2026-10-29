"""缺陷注入规格的公共结构。

引擎在 `backend/tools/inject_defects.py`，本包只放「注什么」。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Injection:
    defect_id: str
    file: str
    """切片内的相对路径。"""
    defect_class: str
    title: str
    rationale: str
    edits: tuple[tuple[str, str], ...]
    """(原文, 替换) 序列。最后一项用于定位 ground truth 的行区间。"""
    triggers_test: str
    """`类名::方法名`，必须能在对应 spec 的 TEST_SOURCE 里找到。"""
