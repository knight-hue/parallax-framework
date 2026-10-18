"""离线反证协议测试。"""

import pytest

from parallax.domain.models import Claim, EvidenceUnit, SourceRef
from parallax.infra.falsifier_llm import LLMFalsifier
from parallax.infra.llm_fake import FakeLLMClient
from parallax.ports.falsifier import OfflineFalsifier


def _claim() -> Claim:
    return Claim(
        claim_id="claim-1",
        fingerprint="module.py#boundary@0",
        statement="空输入会触发边界错误",
        extracted_by="reader-1",
        source_refs=[SourceRef(evidence_id="e1", adapter="test", locator="module.py:1")],
        trigger_conditions=["empty input"],
        counter_conditions=["validated upstream"],
    )


def _evidence(content: str, evidence_id: str = "e1") -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=evidence_id,
        adapter="test",
        locator="module.py:1",
        content=content,
    )


def test_offline_falsifier_confirms_trigger_condition():
    result = OfflineFalsifier().evaluate(_claim(), [_evidence("rejects empty input")])
    assert result.verdict == "confirmed"
    assert result.evidence_ids == ["e1"]


def test_offline_falsifier_preserves_refutation():
    result = OfflineFalsifier().evaluate(_claim(), [_evidence("validated upstream")])
    assert result.verdict == "refuted"
    assert result.status == "refuted"


def test_offline_falsifier_reports_insufficient_evidence():
    result = OfflineFalsifier().evaluate(_claim(), [_evidence("uses a list")])
    assert result.verdict == "insufficient_evidence"


def test_offline_falsifier_ignores_unreferenced_evidence():
    result = OfflineFalsifier().evaluate(_claim(), [_evidence("empty input", "other")])
    assert result.verdict == "insufficient_evidence"
    assert result.evidence_ids == []


@pytest.mark.asyncio
async def test_llm_falsifier_filters_fabricated_evidence_ids():
    client = FakeLLMClient(
        responder=lambda _messages: {
            "verdict": "refuted",
            "reason": "反证条件出现",
            "evidence_ids": ["e1", "fabricated"],
        }
    )
    result = await LLMFalsifier(client).aevaluate(_claim(), [_evidence("validated upstream")])
    assert result.verdict == "refuted"
    assert result.evidence_ids == ["e1"]
    assert "Claim" in client.calls[0][1].content


@pytest.mark.asyncio
async def test_llm_falsifier_fails_closed_on_model_error():
    client = FakeLLMClient(responder=RuntimeError("offline"))
    result = await LLMFalsifier(client).aevaluate(_claim(), [_evidence("anything")])
    assert result.verdict == "insufficient_evidence"
    assert "调用失败" in result.reason
