from parallax.core.independence import analyze_dependencies, build_provenance_graph
from parallax.domain.models import EvidenceUnit
from parallax.engine import ParallaxEngine
from parallax.infra.llm_fake import FakeLLMClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from tests.conftest import make_responder, make_settings


def unit(eid, kind="raw", upstream=()):
    return EvidenceUnit(
        evidence_id=eid,
        locator=eid,
        content="x",
        adapter="test",
        kind=kind,
        derived_from=list(upstream),
    )


def test_transitive_common_summary_collapses_support_but_raw_overlap_does_not():
    evidence = [
        unit("raw"),
        unit("summary", "summary", ["raw"]),
        unit("left", "tool_output", ["summary"]),
        unit("right", "summary", ["summary"]),
    ]
    analysis = analyze_dependencies({"a": ["left"], "b": ["right"], "c": ["raw"]}, evidence)
    assert analysis.support(["a", "b"]) == 1
    assert analysis.support(["a", "b", "c"]) == 2
    assert analysis.common_upstreams == ["summary"]
    assert analyze_dependencies({"a": ["raw"], "b": ["raw"]}, evidence).support(["a", "b"]) == 2


def test_missing_or_cyclic_lineage_never_satisfies_support():
    evidence = [
        unit("a", "summary", ["b"]),
        unit("b", "summary", ["a"]),
        unit("missing", "summary", ["undeclared"]),
    ]
    analysis = analyze_dependencies({"x": ["a"], "y": ["missing"]}, evidence)
    assert analysis.support(["x", "y"]) == 0
    assert "undeclared" in analysis.unresolved


def test_lineage_graph_has_no_dangling_endpoints():
    graph = build_provenance_graph([], {"r": ["a"]}, evidence=[unit("a", "summary", ["missing"])])
    ids = {node.node_id for node in graph.nodes}
    assert all(edge.source in ids and edge.target in ids for edge in graph.edges)


async def test_minimum_support_enforced_without_overlap_violation(demo_repo, defects):
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(demo_repo),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_responder(defects)),
        settings=make_settings(n_readers=2, redundancy=2, min_independent_support=3, max_rounds=1),
    )
    report = await engine.run("审查")
    assert not report.high_confidence
    assert report.pending
    assert all(c.metadata["independent_support"] == 2 for c in report.pending)
    assert all(r.claims_verified == 0 for r in engine.runtime.reputation_store.all())


async def test_shared_upstream_blocks_high_confidence_in_actual_graph(demo_repo, defects):
    class SummaryAdapter(RepoAdapter):
        def load(self, question):
            source = super().load(question)
            return [
                u.model_copy(update={"kind": "summary", "derived_from": ["shared"]}) for u in source
            ] + [unit("shared", "summary")]

    engine = ParallaxEngine.build(
        adapter=SummaryAdapter(demo_repo),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_responder(defects)),
        settings=make_settings(n_readers=3, redundancy=3, max_rounds=1),
    )
    report = await engine.run("审查")
    assert not report.high_confidence
    assert "shared" in report.independence.common_upstreams
    assert report.independence.dependency_channel_count == 1
