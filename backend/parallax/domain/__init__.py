"""领域层：与框架机制直接相关的数据模型，不依赖任何具体场景或基础设施。"""

from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.errors import (
    AdapterError,
    ConfigurationError,
    LLMError,
    ParallaxError,
    ReaderError,
    SchemaValidationError,
)
from parallax.domain.models import (
    AgentReputation,
    Claim,
    CoverageMatrix,
    EvidenceUnit,
    Report,
    ReputationEvent,
    RunManifest,
    SourceRef,
)

__all__ = [
    "AdapterError",
    "AgentReputation",
    "Claim",
    "ClaimStatus",
    "ConfigurationError",
    "CoverageMatrix",
    "EvidenceUnit",
    "LLMError",
    "ParallaxError",
    "Polarity",
    "ReaderError",
    "Report",
    "ReputationEvent",
    "RunManifest",
    "SchemaValidationError",
    "SourceRef",
]
