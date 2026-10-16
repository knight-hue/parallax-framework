"""扩展点 2：Reader 插件。

决定「盲读」具体怎么做：怎么提问、怎么解析、怎么判定两条 claim 是同一主体。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from parallax.domain.models import Claim, EvidenceUnit
from parallax.ports.llm import ChatMessage


@runtime_checkable
class ReaderPlugin(Protocol):
    """盲读 Reader 插件协议。"""

    name: str

    def claim_types(self) -> list[str]:
        """本插件能产出的 claim 类型清单 = 覆盖率矩阵的列维度。"""
        ...

    def output_schema(self) -> type[BaseModel]:
        """期望模型返回的 JSON schema（Pydantic 模型）。

        Reader 会用它做强校验，校验失败按 SchemaValidationError 重试。
        返回 schema 而非自由文本，是「结构化 claim」能成立的前提。
        """
        ...

    def build_messages(
        self,
        question: str,
        shard: list[EvidenceUnit],
        reader_id: str,
    ) -> list[ChatMessage]:
        """构造这个 Reader 这一轮看到的消息。

        ⚠️ 契约：实现**不得**传入 shard 之外的任何证据，也不得传入
        其他 Reader 的产出。这是盲读不被破坏的最后一道防线。
        """
        ...

    def parse(
        self,
        payload: BaseModel,
        shard: list[EvidenceUnit],
        reader_id: str,
        round_index: int,
        reputation: float,
    ) -> list[Claim]:
        """把校验过的模型输出解析成 Claim（含 fingerprint 计算与源指针绑定）。

        指纹规则由插件决定，但必须满足：
            - 确定性：同样输入 → 同样指纹
            - 可区分：不是所有 claim 都塌缩到同一个指纹
            - 语义正确：「同主体不同极性」应共享指纹（这样矛盾才能被检出）
        """
        ...
