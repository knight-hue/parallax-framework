"""扩展点 1：证据适配器。

把任意来源（代码仓库、文档集、论文库、工单快照……）拆成标准 EvidenceUnit。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from parallax.domain.models import EvidenceUnit


@runtime_checkable
class EvidenceAdapter(Protocol):
    """证据适配器协议。"""

    name: str

    def load(self, question: str) -> list[EvidenceUnit]:
        """加载证据。

        Args:
            question: 本次要回答的问题。适配器可以据此决定加载范围
                （例如只加载相关模块，而不是整仓库）。

        Returns:
            标准证据单元列表。`evidence_id` 必须稳定——同一份来源
            在多次运行中必须产出同样的 id，否则 run manifest 无法复盘。
        """
        ...

    def dimension_rows(self, units: list[EvidenceUnit]) -> list[str]:
        """覆盖率矩阵的行维度（「该覆盖什么」）。

        代码审计场景下即模块清单。默认实现取 `unit.group` 的去重集合。
        """
        ...
