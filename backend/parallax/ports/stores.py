"""存储端口。

只定义「上层需要哪些能力」，不关心底层是内存、Redis 还是 Postgres。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from parallax.domain.models import AgentReputation


@runtime_checkable
class ReputationStore(Protocol):
    """Agent 声誉存储。

    声誉是**跨任务累积**的，这是「历史声誉分」这个概念能成立的前提，
    因此实现必须可持久化；内存实现仅用于开发与单测。
    """

    def get(self, agent_id: str, role: str = "reader") -> AgentReputation:
        """取声誉；不存在时以中性分（0.5）创建。"""
        ...

    def save(self, reputation: AgentReputation) -> None: ...

    def all(self) -> list[AgentReputation]: ...
