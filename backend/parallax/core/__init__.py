"""核心机制层：与具体场景无关的五个模块。

    1. Evidence Adapter    → ports/evidence_adapter.py（由插件实现）
    2. Reader Pool         → core/reader_pool.py
    3. Claim Ledger        → core/ledger.py
    4. Aggregator          → core/aggregator.py
    5. Coverage Monitor    → core/coverage.py

外加两个支撑件：partitioning（盲读分区）、reputation（声誉）。
"""

from parallax.core.aggregator import AggregationRules, Aggregator
from parallax.core.coverage import CoverageDecision, CoverageMonitor
from parallax.core.ledger import ClaimLedger, LedgerGroup
from parallax.core.partitioning import BlindPartitioner, Partition
from parallax.core.reputation import InMemoryReputationStore, ReputationPolicy

__all__ = [
    "AggregationRules",
    "Aggregator",
    "BlindPartitioner",
    "ClaimLedger",
    "CoverageDecision",
    "CoverageMonitor",
    "InMemoryReputationStore",
    "LedgerGroup",
    "Partition",
    "ReputationPolicy",
]
