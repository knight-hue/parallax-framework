from parallax.core.semantic_partitioning import SemanticClosurePartitioner
from parallax.domain.models import EvidenceUnit
from parallax.plugins.code_audit.risk_graph import annotate_risk_dependencies


def unit(path, content, group):
    return EvidenceUnit(
        evidence_id=path, locator=path, content=content, group=group, adapter="test"
    )


def test_imported_contract_and_producer_stay_in_risk_context():
    units = annotate_risk_dependencies(
        [
            unit("app/consumer.py", "from app.contract import load\nprint(load())", "app/consumer"),
            unit("app/contract.py", "def load(): return 1", "app/contract"),
        ]
    )
    partitions = SemanticClosurePartitioner(n_readers=2, redundancy=1).partition(
        units, 0, ["app/consumer"]
    )
    active = [partition for partition in partitions if partition.units]
    assert len(active) == 1
    assert set(active[0].evidence_ids) == {"app/consumer.py", "app/contract.py"}


def test_shared_configuration_key_joins_context_and_obeys_cap():
    units = annotate_risk_dependencies(
        [
            unit(f"p/{index}.py", "import os\nx = os.getenv('AUTH_MODE')", f"p/{index}")
            for index in range(5)
        ]
    )
    partitions = SemanticClosurePartitioner(
        n_readers=3, redundancy=1, max_context_units=1
    ).partition(units, 0, ["p/0"])
    assert max(len(partition.units) for partition in partitions) == 2


def test_invalid_syntax_is_reported_without_execution():
    [result] = annotate_risk_dependencies([unit("bad.py", "def !bad", "bad")])
    assert result.metadata["risk_graph_status"] == "unavailable"
