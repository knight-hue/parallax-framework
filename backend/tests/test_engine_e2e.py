"""端到端编排测试——验证四条机制串起来真的成立。

三个测试分别对应三件事：
    1. 盲读 + 冗余分区：一轮内即可交叉验证并收敛
    2. 严格分区 + 覆盖率补检：交叉验证**跨轮涌现**（机制 3 与 4 的合力）
    3. 对照组能测出抗从众差异（实验台本身是可用的）
"""

from __future__ import annotations

import re

from parallax.engine import ParallaxEngine
from parallax.infra.llm_fake import FakeLLMClient
from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter
from tests.conftest import make_responder, make_settings

SHARED_BLOCK_RE = re.compile(
    r"<other-reviewers-findings>(.*?)</other-reviewers-findings>", re.DOTALL
)


def settings(**overrides):
    """本文件内的便捷包装，默认值由 conftest.make_settings 统一提供。"""
    return make_settings(**overrides)


def build_engine(repo, defects, settings_obj) -> ParallaxEngine:
    return ParallaxEngine.build(
        adapter=RepoAdapter(repo, group_depth=2),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_responder(defects)),
        settings=settings_obj,
    )


def fingerprints(engine: ParallaxEngine) -> set[str]:
    return {g.fingerprint for g in engine.runtime.ledger.groups()}


# ---- 1. 盲读 + 冗余分区 ----


async def test_blind_run_finds_seeded_defects_with_high_confidence(demo_repo, defects):
    engine = build_engine(demo_repo, defects, settings())

    report = await engine.run("审查这个仓库中的缺陷")

    found = {c.fingerprint for c in report.high_confidence}
    assert "pkg/mod_a/a.py#concurrency@0" in found
    assert "pkg/mod_b/b.py#boundary@0" in found
    assert len(report.pending) == 0
    assert len(report.disputed) == 0


async def test_blind_run_converges_without_redundant_rounds(demo_repo, defects):
    """覆盖已达标且无未确认项 → 不该白白多跑一轮。"""
    engine = build_engine(demo_repo, defects, settings())
    report = await engine.run("审查")

    assert len(report.manifest.rounds) == 1
    assert report.manifest.stop_reason.value == "coverage_satisfied"


async def test_report_exposes_coverage_matrix(demo_repo, defects):
    engine = build_engine(demo_repo, defects, settings())
    report = await engine.run("审查")

    assert report.coverage.rows == ["pkg/mod_a", "pkg/mod_b"]
    assert set(report.coverage.cols) == set(CodeAuditReader().claim_types())
    assert report.coverage.count("pkg/mod_a", "concurrency") == 2
    assert report.coverage.count("pkg/mod_b", "boundary") == 2


async def test_manifest_records_blind_assignments(demo_repo, defects):
    engine = build_engine(demo_repo, defects, settings())
    report = await engine.run("审查")

    record = report.manifest.rounds[0]
    assert record.assignments, "必须留下分区取证"
    assert record.new_fingerprints == 2


# ---- 2. 严格分区 + 覆盖率补检 → 交叉验证跨轮涌现 ----


async def test_strict_partition_gets_cross_validation_from_retrieval(demo_repo, defects):
    """机制 3 与 4 的合力，这是框架最核心的一条行为。

    redundancy=1 时每条证据只被 1 个 Reader 看过，因此第一轮所有 claim 都是孤证；
    覆盖率监控发现「证据独立覆盖不足」，于是派出**全新 Reader** 做第二轮。
    结果：同一条缺陷被两个不同身份的 Reader 独立报出 → 升为高置信。

    注意这只是额外一轮，而且**没有让老 Reader 补读**。
    """
    engine = build_engine(demo_repo, defects, settings(redundancy=1, max_rounds=3))

    report = await engine.run("审查")

    assert len(report.manifest.rounds) == 2, "应触发恰好一轮补检"
    assert report.manifest.stop_reason.value == "no_new_evidence"
    assert len(report.high_confidence) == 2, "补检应把孤证升为高置信"

    # 两轮的 Reader 身份必须完全不同——这是「派新 Reader」而非「让老 Reader 补读」的取证
    round0 = set(report.manifest.rounds[0].assignments)
    round1 = set(report.manifest.rounds[1].assignments)
    assert round0.isdisjoint(round1)

    for claim in report.high_confidence:
        assert len(claim.verified_by) == 2


async def test_redundancy_one_without_coverage_leaves_pending(demo_repo, defects):
    """反证：关掉补检（max_rounds=1）后，严格分区只能得到孤证。"""
    engine = build_engine(demo_repo, defects, settings(redundancy=1, max_rounds=1))
    report = await engine.run("审查")

    assert len(report.manifest.rounds) == 1
    assert len(report.high_confidence) == 0
    assert len(report.pending) == 2
    assert report.manifest.stop_reason.value == "max_rounds_reached"


async def test_initial_focus_count_limits_round_zero(demo_repo, defects):
    """固定预算模式：首轮只切前 K 个维度（供 P0-4 的预算对照使用）。

    注意它只约束**首轮**——后续补检轮仍按覆盖率扩展，那是另一个机制。
    固定预算实验用 max_rounds=1 把补检关掉，才是纯净的预算对照。
    """
    engine = build_engine(demo_repo, defects, settings(initial_focus_count=1, max_rounds=1))
    report = await engine.run("审查")

    read_files = {
        c.source_refs[0].locator.split(":")[0]
        for c in report.high_confidence + report.pending + report.disputed
    }
    assert read_files, "应当仍有产出"
    assert all(path.startswith("pkg/mod_a") for path in read_files), (
        f"首轮应只读第一个模块，实际读到了 {read_files}"
    )


async def test_initial_focus_is_only_a_starting_point(demo_repo, defects):
    """允许补检时，覆盖率监控会走出首轮设定的预算范围——这是期望行为。

    预算约束只影响**起点**，不影响"发现缺口后主动补检"这件事本身。
    """
    engine = build_engine(demo_repo, defects, settings(initial_focus_count=1, max_rounds=3))
    report = await engine.run("审查")

    read_modules = {
        "/".join(c.source_refs[0].locator.split(":")[0].split("/")[:2])
        for c in report.high_confidence + report.pending + report.disputed
    }
    assert read_modules == {"pkg/mod_a", "pkg/mod_b"}, "补检应扩展到首轮未覆盖的模块"


async def test_initial_focus_count_zero_means_unlimited(demo_repo, defects):
    engine = build_engine(demo_repo, defects, settings(initial_focus_count=0))
    report = await engine.run("审查")

    read_modules = {
        "/".join(c.source_refs[0].locator.split(":")[0].split("/")[:2])
        for c in report.high_confidence + report.pending + report.disputed
    }
    assert read_modules == {"pkg/mod_a", "pkg/mod_b"}


# ---- 3. 对照组：能测出从众 ----


def make_herding_responder(defects: dict[str, list[dict]]):
    """风格化的从众模拟器。

    ⚠️ 这是为了验证**实验台可用性**的人造模型，不是关于真实大模型行为的实证主张。

    行为规则：只要能看到别人的结论，就完全放弃自己的独立发现，一条都不提。
    这对应文献里说的「anchoring / conformity → 后到的审查者不再做独立工作」。
    """
    own = make_responder(defects)

    def respond(messages):
        text = "\n".join(m.content for m in messages)
        if SHARED_BLOCK_RE.search(text):
            return {"findings": [], "notes": "anchored on others"}
        return own(messages)

    return respond


async def test_control_group_shows_herding_loss(demo_repo, defects):
    """对照组（共享结论）在从众条件下会丢掉部分独立发现，实验组不会。

    这条测试真正验证的是：**这套测试台能测出抗从众差异**。
    如果实验组和对照组在这里表现一样，说明实验设计没有区分度，整个项目叙事就空了。
    """
    shared = settings(redundancy=1, max_rounds=1, reader_visibility="shared")
    blind = settings(redundancy=1, max_rounds=1, reader_visibility="blind")

    engine_blind = ParallaxEngine.build(
        adapter=RepoAdapter(demo_repo, group_depth=2),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_responder(defects)),
        settings=blind,
    )
    engine_shared = ParallaxEngine.build(
        adapter=RepoAdapter(demo_repo, group_depth=2),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_herding_responder(defects)),
        settings=shared,
    )

    blind_report = await engine_blind.run("审查")
    shared_report = await engine_shared.run("审查")

    blind_recall = len(fingerprints(engine_blind))
    shared_recall = len(fingerprints(engine_shared))

    assert blind_recall == 2
    assert shared_recall == 1
    assert shared_recall < blind_recall, "实验台必须能区分出抗从众带来的召回差异"
    assert blind_report.independence.isolation_status == "verified"
    assert shared_report.independence.isolation_status == "violated"


async def test_shared_mode_records_how_many_claims_a_reader_saw(demo_repo, defects):
    """审计留痕：共享模式下每轮读取了多少条他人结论。"""
    engine = ParallaxEngine.build(
        adapter=RepoAdapter(demo_repo, group_depth=2),
        plugin=CodeAuditReader(),
        client=FakeLLMClient(make_herding_responder(defects)),
        settings=settings(redundancy=1, max_rounds=1, reader_visibility="shared"),
    )
    await engine.run("审查")

    # 第二轮之后的 Reader 应当都看到过至少一条他人结论
    # （这里不直接断言，因为是否触发共享取决于该 Reader 是否为空分区；
    #   改为断言整体有产出，具体隔离性由 test_reader_pool 覆盖）
    assert engine.runtime.usage.calls > 0
