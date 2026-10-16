"""评测指标测试（纯函数，不需要模型）。"""

from __future__ import annotations

import pytest

from parallax.domain.models import Claim, SourceRef
from parallax.eval.corpus import GroundTruth, PlantedDefect, Task, verify_task
from parallax.eval.metrics import effective_channels, match_claims, parse_location


def defect(did: str, file: str, start: int, end: int, cls: str = "logic") -> PlantedDefect:
    return PlantedDefect(
        id=did,
        file=file,
        line_start=start,
        line_end=end,
        defect_class=cls,
        title=f"defect {did}",
        marker="x = 1",
    )


def claim(
    file: str,
    start: int,
    end: int,
    agent: str = "r1",
    fingerprint: str | None = None,
    claim_id: str | None = None,
) -> Claim:
    return Claim(
        claim_id=claim_id or f"{file}:{start}-{end}:{agent}",
        fingerprint=fingerprint or f"{file}#logic@{start // 20 * 20}",
        statement="s",
        claim_type="logic",
        extracted_by=agent,
        source_refs=[SourceRef(evidence_id="e1", adapter="t", locator=f"{file}:{start}-{end}")],
        metadata={"line_start": start, "line_end": end},
    )


# ---- 定位解析 ----


def test_parse_location_prefers_metadata():
    loc = parse_location(claim("a/b.py", 10, 12))
    assert loc is not None
    assert loc.file == "a/b.py"
    assert (loc.start, loc.end) == (10, 12)


def test_parse_location_falls_back_to_locator():
    c = claim("a/b.py", 10, 12)
    c.metadata.clear()
    loc = parse_location(c)
    assert loc is not None
    assert (loc.file, loc.start, loc.end) == ("a/b.py", 10, 12)


def test_parse_location_normalises_windows_paths():
    c = claim("a\\b.py", 1, 2)
    loc = parse_location(c)
    assert loc is not None and loc.file == "a/b.py"


# ---- 匹配 ----


def test_exact_hit():

    match = match_claims([claim("a.py", 10, 12)], [defect("D1", "a.py", 10, 12)])
    assert match.hits == 1
    assert match.defects[0].found_by == ["r1"]


def test_line_drift_within_tolerance_still_hits():
    """两个 Agent 对同一缺陷给出的行号不会完全一致，必须容忍。"""
    match = match_claims([claim("a.py", 30, 32)], [defect("D1", "a.py", 10, 12)])
    assert match.hits == 1


def test_too_far_away_is_unmatched():
    match = match_claims([claim("a.py", 200, 202)], [defect("D1", "a.py", 10, 12)])
    assert match.hits == 0
    assert match.matches[0].verdict == "unmatched"


def test_wrong_file_never_matches():
    match = match_claims([claim("b.py", 10, 12)], [defect("D1", "a.py", 10, 12)])
    assert match.hits == 0


def test_two_agents_on_same_defect_both_counted_as_finders():
    """核心断言：交叉验证数必须把第二条（冗余）claim 也算进去。

    漏掉它会让「孤证数」虚高，而孤证数是衡量从众的核心指标。
    """
    claims = [
        claim("a.py", 10, 12, agent="r1"),
        claim("a.py", 11, 13, agent="r2"),
    ]
    match = match_claims(claims, [defect("D1", "a.py", 10, 12)])

    assert match.hits == 1
    assert match.defects[0].found_by == ["r1", "r2"]
    assert match.duplicates == 1


def test_class_mismatch_still_counts_as_hit():
    """匹配以位置为主——问的是「找到没有」，不是「类目标签是否与出题人一致」。"""
    match = match_claims([claim("a.py", 10, 12)], [defect("D1", "a.py", 10, 12, "security")])
    assert match.hits == 1


def test_nearest_claim_wins_assignment():
    """近距离的 claim 优先占用缺陷，避免「先到先得」把好匹配浪费掉。"""
    claims = [
        claim("a.py", 60, 62, agent="r1"),  # 距离 48
        claim("a.py", 10, 12, agent="r2"),  # 精确命中
    ]
    match = match_claims(claims, [defect("D1", "a.py", 10, 12)], line_tolerance=50)
    assert match.defects[0].found_by == ["r1", "r2"]
    verdicts = {m.agent: m.verdict for m in match.matches}
    assert verdicts["r2"] == "hit", "精确命中的 claim 应占位为 hit"
    assert verdicts["r1"] == "duplicate"


def test_claim_beyond_tolerance_is_unmatched():
    """超出容忍窗口的 claim 不能被算作该缺陷的证据。"""
    match = match_claims(
        [claim("a.py", 60, 62, agent="r1"), claim("a.py", 10, 12, agent="r2")],
        [defect("D1", "a.py", 10, 12)],
        line_tolerance=10,
    )
    assert match.defects[0].found_by == ["r2"]
    assert {m.verdict for m in match.matches} == {"hit", "unmatched"}


def test_missing_defect_is_reported():
    match = match_claims(
        [claim("a.py", 10, 12)], [defect("D1", "a.py", 10, 12), defect("D2", "a.py", 90, 92)]
    )
    assert match.hits == 1
    assert [d.defect_id for d in match.defects if not d.hit] == ["D2"]


# ---- K* ----


def test_k_star_is_one_when_agents_are_identical():
    same = {"f1", "f2", "f3"}
    assert effective_channels({"a": same, "b": set(same), "c": set(same)}) == 1.0


def test_k_star_equals_agent_count_when_fully_disjoint():
    assert effective_channels({"a": {"f1"}, "b": {"f2"}, "c": {"f3"}}) == 3.0


def test_k_star_stays_within_one_and_n():
    """这是第一版公式出错的地方：少了平方会算出大于 N 的值。"""
    sets = {
        "a": {"f1", "f2", "f3", "f4"},
        "b": {"f1", "f2", "f5", "f6"},
        "c": {"f3", "f4", "f5", "f7"},
    }
    k = effective_channels(sets)
    assert 1.0 <= k <= 3.0


def test_k_star_edge_cases():
    assert effective_channels({}) == 0.0
    assert effective_channels({"a": set()}) == 0.0
    assert effective_channels({"a": {"f1"}}) == 1.0


# ---- 语料完整性 ----


def test_verify_task_catches_drifted_line_numbers(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")

    good = Task(
        task_id="t",
        root=tmp_path,
        repo_path=repo,
        ground_truth=GroundTruth(task_id="t", defects=[defect("D1", "a.py", 1, 1)]),
        question="q",
    )
    assert verify_task(good) == []

    # marker 写成 y = 2 但行号指向第 1 行 → 必须被抓到
    drifted = defect("D1", "a.py", 1, 1)
    drifted.marker = "y = 2"
    bad = good.model_copy(update={"ground_truth": GroundTruth(task_id="t", defects=[drifted])})
    problems = verify_task(bad)
    assert problems and "marker" in problems[0]


def test_ground_truth_count_mismatch_is_rejected():
    truth = GroundTruth(task_id="t", planted_defect_count=5, defects=[defect("D1", "a.py", 1, 1)])
    with pytest.raises(ValueError):
        truth.validate_count()


# ---- K* 的口径：必须与 Agent 数一起读 ----


def test_k_star_is_bounded_by_agent_count():
    """K* 值域 [1, agent_count]。这是它可解释的前提。"""
    agent_fps = {f"a{i}": {f"fp{i}"} for i in range(6)}
    k = effective_channels(agent_fps)
    assert k == 6, "完全互斥时 K* 应等于 Agent 数"


def test_multi_round_raises_the_ceiling_of_k_star():
    """多轮换新身份会把 K* 的上限从 6 抬到 18——这正是裸 K* 不可跨臂比较的原因。"""
    single_round = {f"reader-r0-{i}": {f"r0-{i}"} for i in range(6)}
    three_rounds = {f"reader-r{r}-{i}": {f"r{r}-{i}"} for r in range(3) for i in range(6)}
    assert effective_channels(single_round) == 6
    assert effective_channels(three_rounds) == 18


def test_channels_ratio_normalises_across_different_agent_counts():
    """归一化占比让"1 轮 6 Agent"与"3 轮 18 Agent"可比。"""
    from parallax.eval.metrics import ArmMetrics

    a = ArmMetrics(arm="x", task_id="t", effective_channels=3.0, agent_count=6)
    b = ArmMetrics(arm="y", task_id="t", effective_channels=9.0, agent_count=18)
    assert a.channels_ratio == 0.5
    assert b.channels_ratio == 0.5, "两者独立性相同，裸 K* 差 3 倍但占比应相等"


def test_channels_ratio_is_zero_without_agents():
    from parallax.eval.metrics import ArmMetrics

    assert ArmMetrics(arm="x", task_id="t").channels_ratio == 0.0
