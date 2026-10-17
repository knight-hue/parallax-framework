"""抽象端口（ports）。

本框架的可插拔性由四个边界清晰的扩展点构成：

    EvidenceAdapter   证据从哪来、怎么切成标准单元、按什么维度切分区
    ReaderPlugin      盲读 Reader 怎么问、怎么解析、怎么给 claim 打指纹
    ClaimValidator    入账前的额外校验（可选，可串联多个）
    Falsifier         Claim 的独立反证/验证（可选）

除此之外的一切（分区、账本、聚合、覆盖率、编排）都是框架职责，
插件不应该也不需要介入——这是「抽象够用就行，不过度设计」的落地。
"""

from parallax.ports.claim_validator import ClaimValidator, ValidationResult
from parallax.ports.evidence_adapter import EvidenceAdapter
from parallax.ports.falsifier import Falsifier, FalsifierResult, OfflineFalsifier
from parallax.ports.llm import ChatMessage, LLMClient
from parallax.ports.reader_plugin import ReaderPlugin
from parallax.ports.stores import ReputationStore

__all__ = [
    "ChatMessage",
    "ClaimValidator",
    "EvidenceAdapter",
    "Falsifier",
    "FalsifierResult",
    "LLMClient",
    "ReaderPlugin",
    "OfflineFalsifier",
    "ReputationStore",
    "ValidationResult",
]
