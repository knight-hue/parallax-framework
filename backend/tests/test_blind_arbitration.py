"""结论剥离仲裁的单元测试。

覆盖三件事：
1. `Observation` 里**没有**结论文本（剥离是结构性的，不靠约定）；
2. 四类缺陷信号在"有缺陷 / 已设防 / 看不出"三种代码上都给出正确三态；
3. 裁决由证据决定，不由人数决定——三人错、一人对时不能按多数走。
"""

from __future__ import annotations

import pytest

from parallax.core.arbitration import (
    BlindArbitrator,
    ObservationLedger,
    RelayArbitrator,
    StickyArbitrator,
    inspect,
    observation_view,
    statement_digest,
)
from parallax.core.ledger import LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import Claim, EvidenceUnit, SourceRef

DEFECTIVE = {
    "business_invariant": """
    public void transfer(String from, String to, long amount) {
        long fromBalance = balances.getOrDefault(from, 0L);
        balances.put(from, fromBalance - amount);
    }
    """,
    "atomicity": """
    public void export(Path target, String content) throws IOException {
        Files.writeString(target, content, StandardCharsets.UTF_8);
        if (content.contains("FAIL")) {
            throw new IOException("rejected");
        }
    }
    """,
    "concurrency": """
    public boolean tryAcquire() {
        long now = clock.millis();
        long elapsedSeconds = (now - lastRefillMillis) / 1000;
        lastRefillMillis = now;
        return tokens > 0;
    }
    """,
    "error_handling": """
    public int getInt(String key) {
        try {
            return Integer.parseInt(values.get(key));
        } catch (NumberFormatException ex) {
            return 0;
        }
    }
    """,
}

GUARDED = {
    "business_invariant": """
    public void transfer(String from, String to, long amount) {
        long fromBalance = balances.getOrDefault(from, 0L);
        if (fromBalance < amount) {
            throw new IllegalStateException("insufficient");
        }
        balances.put(from, fromBalance - amount);
    }
    """,
    "atomicity": """
    public void export(Path target, String content) throws IOException {
        if (content.contains("FAIL")) {
            throw new IOException("rejected");
        }
        Path temporary = Files.createTempFile(directory, ".report-", ".tmp");
        Files.writeString(temporary, content, StandardCharsets.UTF_8);
    }
    """,
    "concurrency": """
    public boolean tryAcquire() {
        long elapsedMillis = clock.millis() - lastRefillMillis;
        if (elapsedMillis >= 1000) {
            long wholeSeconds = elapsedMillis / 1000;
            lastRefillMillis += wholeSeconds * 1000;
        }
        return tokens > 0;
    }
    """,
    "error_handling": """
    public int getInt(String key) {
        try {
            return Integer.parseInt(values.get(key));
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException("invalid", ex);
        }
    }
    """,
}


def _unit(content: str, locator: str = "Sample.java:1-20") -> EvidenceUnit:
    return EvidenceUnit(evidence_id="ev-1", adapter="test", locator="Sample.java", content=content)


def _claim(
    *,
    polarity: Polarity,
    claim_type: str,
    agent: str,
    locator: str = "Sample.java:1-20",
    statement: str = "样本结论",
) -> Claim:
    return Claim(
        claim_id=f"c-{agent}",
        fingerprint="Sample.java#claim@v1",
        statement=statement,
        polarity=polarity,
        claim_type=claim_type,
        extracted_by=agent,
        source_refs=[SourceRef(evidence_id="ev-1", adapter="test", locator=locator)],
    )


def _group(claims: list[Claim]) -> LedgerGroup:
    return LedgerGroup(
        fingerprint=claims[0].fingerprint,
        claim_ids=[claim.claim_id for claim in claims],
        asserting_agents=[c.extracted_by for c in claims if c.polarity == Polarity.ASSERT],
        denying_agents=[c.extracted_by for c in claims if c.polarity == Polarity.DENY],
    )


# ---- 观察视图 ----


def test_observation_view_has_no_statement():
    claim = _claim(
        polarity=Polarity.ASSERT, claim_type="concurrency", agent="r1", statement="这里有竞态"
    )
    view = observation_view(claim)
    dumped = view.model_dump()
    assert "statement" not in dumped
    assert "这里有竞态" not in str(dumped)
    assert view.polarity == Polarity.ASSERT
    assert view.locator == claim.source_refs[0].locator


def test_observation_ledger_keeps_digests_only():
    claims = [
        _claim(
            polarity=Polarity.ASSERT, claim_type="atomicity", agent="r1", statement="先写后校验"
        ),
        _claim(polarity=Polarity.DENY, claim_type="atomicity", agent="r2", statement="顺序没问题"),
    ]
    ledger = ObservationLedger.build(_group(claims), claims)
    assert ledger.statement_digests["c-r1"] == statement_digest("先写后校验")
    assert ledger.statement_digests["c-r2"] == statement_digest("顺序没问题")
    assert all("statement" not in observation.model_dump() for observation in ledger.observations)
    # 摘要不可逆：既不等于原文，也不会泄露原文
    assert "先写后校验" not in str(ledger.statement_digests)


# ---- 证据信号 ----


@pytest.mark.parametrize("claim_type", sorted(DEFECTIVE))
def test_inspect_confirms_on_defective_code(claim_type: str):
    assert inspect(claim_type, DEFECTIVE[claim_type], "Sample.java:1-20") == "confirms_defect"


@pytest.mark.parametrize("claim_type", sorted(GUARDED))
def test_inspect_refutes_on_guarded_code(claim_type: str):
    assert inspect(claim_type, GUARDED[claim_type], "Sample.java:1-20") == "refutes_defect"


def test_inspect_is_inconclusive_for_unknown_type_and_missing_window():
    assert inspect("naming", DEFECTIVE["atomicity"], "Sample.java:1-20") == "inconclusive"
    assert inspect("atomicity", "", "Sample.java:1-20") == "inconclusive"
    assert inspect("atomicity", "int x = 1;", "not-a-locator") == "inconclusive"


def test_inspect_respects_locator_window():
    """同一份文件里的两段代码，窗口不同 → 信号不同。"""
    defect_lines = [
        "class A {",
        "    public void transfer(long amount) {",
        "        balances.put(from, fromBalance - amount);",
        "    }",
    ]
    guard_lines = [
        "    public void transfer(long amount) {",
        "        if (fromBalance < amount) {",
        '            throw new IllegalStateException("insufficient");',
        "        }",
        "        balances.put(from, fromBalance - amount);",
        "    }",
    ]
    separator = ["    // ----"] * 4
    mixed = "\n".join(defect_lines + separator + guard_lines)
    guard_start = len(defect_lines) + len(separator) + 1
    guard_end = guard_start + len(guard_lines) - 1

    assert inspect("business_invariant", mixed, "A.java:2-3") == "confirms_defect"
    assert (
        inspect("business_invariant", mixed, f"A.java:{guard_start}-{guard_end}")
        == "refutes_defect"
    )


# ---- 裁决 ----


@pytest.mark.asyncio
async def test_arbitration_follows_evidence_not_majority():
    """三人说没问题、一人说有 bug，证据说有 → 不能按多数判成"没问题"。"""
    claims = [
        _claim(polarity=Polarity.DENY, claim_type="concurrency", agent=f"wrong-{i}")
        for i in range(3)
    ] + [_claim(polarity=Polarity.ASSERT, claim_type="concurrency", agent="right")]
    arbitrator = BlindArbitrator()
    arbitrator.bind_evidence({"ev-1": _unit(DEFECTIVE["concurrency"])})

    verdict = await arbitrator.arbitrate(_group(claims), claims)

    assert verdict == ClaimStatus.HIGH_CONFIDENCE
    assert all(claim.metadata["arbitration_input"] == "observation-only" for claim in claims)


@pytest.mark.asyncio
async def test_arbitration_refutes_when_evidence_is_guarded():
    claims = [
        _claim(polarity=Polarity.ASSERT, claim_type="business_invariant", agent=f"wrong-{i}")
        for i in range(3)
    ] + [_claim(polarity=Polarity.DENY, claim_type="business_invariant", agent="right")]
    arbitrator = BlindArbitrator()
    arbitrator.bind_evidence({"ev-1": _unit(GUARDED["business_invariant"])})

    assert await arbitrator.arbitrate(_group(claims), claims) == ClaimStatus.PENDING


@pytest.mark.asyncio
async def test_arbitration_escalates_when_evidence_is_silent():
    claims = [
        _claim(polarity=Polarity.ASSERT, claim_type="error_handling", agent="a"),
        _claim(polarity=Polarity.DENY, claim_type="error_handling", agent="b"),
    ]
    arbitrator = BlindArbitrator()
    arbitrator.bind_evidence({"ev-1": _unit("public int answer() { return 42; }")})

    assert await arbitrator.arbitrate(_group(claims), claims) == ClaimStatus.DISPUTED


@pytest.mark.asyncio
async def test_arbitration_escalates_when_evidence_not_bound():
    claims = [
        _claim(polarity=Polarity.ASSERT, claim_type="concurrency", agent="a"),
        _claim(polarity=Polarity.DENY, claim_type="concurrency", agent="b"),
    ]
    assert await BlindArbitrator().arbitrate(_group(claims), claims) == ClaimStatus.DISPUTED


@pytest.mark.asyncio
async def test_relay_arbitrator_follows_headcount():
    claims = [
        _claim(polarity=Polarity.DENY, claim_type="concurrency", agent=f"wrong-{i}")
        for i in range(3)
    ] + [_claim(polarity=Polarity.ASSERT, claim_type="concurrency", agent="right")]

    verdict = await RelayArbitrator().arbitrate(_group(claims), claims)

    assert verdict == ClaimStatus.PENDING  # 多数派说没问题 → 中继仲裁照抄
    assert all(claim.metadata["arbitration_input"] == "statement-visible" for claim in claims)


@pytest.mark.asyncio
async def test_sticky_arbitrator_endpoints_match_blind_and_relay():
    claims = [
        _claim(polarity=Polarity.DENY, claim_type="concurrency", agent=f"wrong-{i}")
        for i in range(3)
    ] + [_claim(polarity=Polarity.ASSERT, claim_type="concurrency", agent="right")]
    evidence = {"ev-1": _unit(DEFECTIVE["concurrency"])}

    blind = StickyArbitrator(stickiness=0.0)
    blind.bind_evidence(evidence)
    relay = StickyArbitrator(stickiness=1.0)
    relay.bind_evidence(evidence)

    assert await blind.arbitrate(_group(claims), claims) == ClaimStatus.HIGH_CONFIDENCE
    assert await relay.arbitrate(_group(claims), claims) == ClaimStatus.PENDING


def test_sticky_arbitrator_rejects_out_of_range():
    with pytest.raises(ValueError):
        StickyArbitrator(stickiness=1.5)


def test_llm_arbitrator_render_can_hide_the_conclusion():
    """真实模型仲裁也必须能剥结论：redact=True 时提示里不得出现 statement。"""
    from parallax.infra.arbitrator_llm import LLMArbitrator

    claim = _claim(
        polarity=Polarity.ASSERT,
        claim_type="concurrency",
        agent="r1",
        statement="这里有明确的竞态条件",
    )

    visible = LLMArbitrator._render(claim, redact=False)
    hidden = LLMArbitrator._render(claim, redact=True)

    assert "这里有明确的竞态条件" in visible
    assert "这里有明确的竞态条件" not in hidden
    assert "主张问题存在" in hidden
    assert "Sample.java:1-20" in hidden
