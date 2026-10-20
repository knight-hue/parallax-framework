"""Framework-neutral JSON/JSONL and callback adapters; no orchestrator SDK needed."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, Field, model_validator

from parallax.core.independence import build_independence_profile, build_provenance_graph
from parallax.domain.models import AuditReceipt, Claim, EvidenceUnit
from parallax.util import stable_id


class ReceiptBundle(BaseModel):
    run_id: str
    producer: str
    evidence: list[EvidenceUnit] = Field(default_factory=list, max_length=5000)
    claims: list[Claim] = Field(default_factory=list, max_length=20_000)
    receipts: list[AuditReceipt] = Field(default_factory=list, max_length=50_000)
    assignments: dict[str, list[str]] = Field(default_factory=dict)
    output_isolation: bool | None = None

    @model_validator(mode="after")
    def validate_references(self):
        evidence = {unit.evidence_id for unit in self.evidence}
        claims = {claim.claim_id for claim in self.claims}
        if len(evidence) != len(self.evidence) or len(claims) != len(self.claims):
            raise ValueError("duplicate evidence or claim IDs")
        receipt_ids: set[str] = set()
        for receipt in self.receipts:
            if receipt.run_id != self.run_id or receipt.receipt_id in receipt_ids:
                raise ValueError("mixed run or duplicate receipt ID")
            receipt_ids.add(receipt.receipt_id)
            if not set(receipt.evidence_ids) <= evidence or not set(receipt.claim_ids) <= claims:
                raise ValueError("receipt has dangling references")
        for assigned in self.assignments.values():
            if not set(assigned) <= evidence:
                raise ValueError("assignment has dangling evidence")
        for claim in self.claims:
            if not {ref.evidence_id for ref in claim.source_refs} <= set(
                self.assignments.get(claim.extracted_by, [])
            ):
                raise ValueError("claim cites evidence outside its reader partition")
        return self

    def audit(self) -> dict:
        profile = build_independence_profile(
            self.claims,
            self.assignments,
            evidence=self.evidence,
            output_contamination=self.output_isolation is False,
        )
        if self.output_isolation is None:
            profile.isolation_status = "unknown"
        return {
            "run_id": self.run_id,
            "producer": self.producer,
            "trust_boundary": "producer-declared facts; no independent attestation",
            "independence": profile.model_dump(mode="json"),
            "provenance": build_provenance_graph(
                self.claims, self.assignments, self.receipts, evidence=self.evidence
            ).model_dump(mode="json"),
        }


def export_jsonl(receipts: Iterable[AuditReceipt]) -> str:
    return "".join(receipt.model_dump_json() + "\n" for receipt in receipts)


def import_jsonl(text: str) -> list[AuditReceipt]:
    receipts = [
        AuditReceipt.model_validate_json(line) for line in text.splitlines() if line.strip()
    ]
    keys = [(receipt.run_id, receipt.receipt_id) for receipt in receipts]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate receipt ID")
    return receipts


class CallbackReceiptAdapter:
    """Attach to a graph callback, message bus, or agent tool-completion hook.

    The producer supplies isolation facts explicitly. Import cannot attest to
    hidden prompts or undisclosed tools in another framework.
    """

    def __init__(self, run_id: str, event_kinds: Mapping[str, str]) -> None:
        self.run_id = run_id
        self.event_kinds = dict(event_kinds)
        self.receipts: list[AuditReceipt] = []

    def on_event(
        self,
        event: str,
        *,
        actor_id: str | None = None,
        evidence_ids: Iterable[str] = (),
        claim_ids: Iterable[str] = (),
        payload: dict | None = None,
        round_index: int = 0,
    ) -> AuditReceipt:
        if event not in self.event_kinds:
            raise ValueError(f"unmapped external event: {event}")
        receipt = AuditReceipt(
            receipt_id=stable_id(self.run_id, event, len(self.receipts)),
            run_id=self.run_id,
            kind=self.event_kinds[event],
            actor_id=actor_id,
            evidence_ids=list(evidence_ids),
            claim_ids=list(claim_ids),
            payload=payload or {},
            round_index=round_index,
        )
        self.receipts.append(receipt)
        return receipt
