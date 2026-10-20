import pytest

from parallax.domain.models import EvidenceUnit
from parallax.ports.receipts import (
    CallbackReceiptAdapter,
    ReceiptBundle,
    export_jsonl,
    import_jsonl,
)


def test_callback_and_jsonl_adapters_roundtrip():
    graph = CallbackReceiptAdapter("run", {"node_finished": "reader"})
    message_bus = CallbackReceiptAdapter("run", {"agent.result": "reader"})
    first = graph.on_event("node_finished", actor_id="a", evidence_ids=["e"])
    second = message_bus.on_event("agent.result", actor_id="b", evidence_ids=["e"])
    assert import_jsonl(export_jsonl([first, second])) == [first, second]


def test_external_bundle_does_not_invent_attested_isolation():
    bundle = ReceiptBundle(
        run_id="run",
        producer="other-orchestrator",
        evidence=[EvidenceUnit(evidence_id="e", locator="a", content="x", adapter="t")],
        assignments={"r": ["e"]},
    )
    assert bundle.audit()["independence"]["isolation_status"] == "unknown"


def test_unknown_events_versions_and_duplicate_receipts_are_rejected():
    adapter = CallbackReceiptAdapter("run", {"node": "reader"})
    receipt = adapter.on_event("node")
    with pytest.raises(ValueError, match="unmapped"):
        adapter.on_event("mystery")
    with pytest.raises(ValueError, match="duplicate"):
        import_jsonl(export_jsonl([receipt, receipt]))
    with pytest.raises(ValueError):
        import_jsonl(
            receipt.model_dump_json().replace("parallax.receipt/v1", "parallax.receipt/v2")
        )


def test_bundle_rejects_dangling_refs_and_mixed_runs():
    adapter = CallbackReceiptAdapter("wrong", {"node": "reader"})
    with pytest.raises(ValueError, match="mixed run"):
        ReceiptBundle(run_id="run", producer="x", receipts=[adapter.on_event("node")])
    with pytest.raises(ValueError, match="dangling"):
        ReceiptBundle(run_id="run", producer="x", assignments={"r": ["missing"]})
