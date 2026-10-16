"""盲读分区测试。

重点验证「不重叠」这个说法被落在两条可验证的约束上：
  ① 每条证据恰好被 redundancy 个 Reader 看到
  ② 同一轮的 Reader 身份互不相同，且跨轮一定换新身份
"""

from __future__ import annotations

import pytest

from parallax.core.partitioning import BlindPartitioner
from parallax.domain.errors import ConfigurationError
from tests.conftest import make_unit


def units(n: int = 6, groups: int = 3) -> list:
    out = []
    for i in range(n):
        group = f"mod{i % groups}"
        out.append(make_unit(f"{group}/f{i}.py", f"# file {i}\n", group))
    return out


def test_redundancy_is_exact_and_uniform():
    partitioner = BlindPartitioner(n_readers=3, redundancy=2, seed=1)
    parts = partitioner.partition(units(), round_index=0)

    counts = partitioner.redundancy_of(parts)
    assert set(counts.values()) == {2}, "每条证据必须恰好被 2 个 Reader 看到"


def test_strict_partition_cannot_cross_validate():
    """redundancy=1 时没有任何证据被两个 Reader 共享——这是原方案字面表述的后果。"""
    partitioner = BlindPartitioner(n_readers=3, redundancy=1, seed=1)
    parts = partitioner.partition(units(), round_index=0)

    counts = partitioner.redundancy_of(parts)
    assert set(counts.values()) == {1}


def test_partition_is_deterministic():
    a = BlindPartitioner(3, 2, seed=7).partition(units(), round_index=0)
    b = BlindPartitioner(3, 2, seed=7).partition(units(), round_index=0)
    assert [p.evidence_ids for p in a] == [p.evidence_ids for p in b]

    c = BlindPartitioner(3, 2, seed=8).partition(units(), round_index=0)
    assert [p.evidence_ids for p in a] != [p.evidence_ids for p in c]


def test_reader_identity_is_fresh_each_round():
    """补检必须派新 Reader——这是「不破坏盲读」在代码上的取证。"""
    partitioner = BlindPartitioner(3, 2, seed=0)
    round0 = {p.reader_id for p in partitioner.partition(units(), round_index=0)}
    round1 = {p.reader_id for p in partitioner.partition(units(), round_index=1)}
    assert round0.isdisjoint(round1)


def test_reader_id_sets_are_isolated():
    partitioner = BlindPartitioner(3, 2, seed=0)
    parts = partitioner.partition(units(), round_index=0)
    assert partitioner.isolation_ok(parts)


def test_group_locality_within_a_reader():
    """同一模块的文件不应被拆给互不相干的 Reader（避免残缺上下文造假缺陷）。"""
    partitioner = BlindPartitioner(n_readers=3, redundancy=1, seed=0)
    parts = partitioner.partition(units(n=9, groups=3), round_index=0)

    seen: dict[str, set[str]] = {}
    for part in parts:
        for unit in part.units:
            seen.setdefault(unit.group, set()).add(part.reader_id)
    # 每个模块只落在一个 Reader 手上（redundancy=1 时）
    assert all(len(readers) == 1 for readers in seen.values()), seen


def test_focus_groups_restrict_scope():
    partitioner = BlindPartitioner(n_readers=2, redundancy=1, seed=0)
    parts = partitioner.partition(units(), round_index=1, focus_groups=["mod1"])
    got = {u.group for part in parts for u in part.units}
    assert got == {"mod1"}


def test_empty_focus_yields_empty_partitions():
    partitioner = BlindPartitioner(n_readers=2, redundancy=1, seed=0)
    parts = partitioner.partition(units(), round_index=1, focus_groups=["does-not-exist"])
    assert all(not p.units for p in parts)


def test_invalid_configuration_rejected():
    with pytest.raises(ConfigurationError):
        BlindPartitioner(n_readers=2, redundancy=3)
    with pytest.raises(ConfigurationError):
        BlindPartitioner(n_readers=0, redundancy=1)


def test_fixed_budget_arms_cost_the_same_but_cover_differently():
    """固定预算实验的核心断言（对应 P0-4）。

    同样花 6 次文件读取：
        共享式（所有人读同一模块）→ 唯一覆盖 2 个文件
        分区式（各读不同模块）    → 唯一覆盖 6 个文件
    这就是「预算全花在重复阅读上」与「预算换成覆盖面」的差别。
    """
    pool = units(n=6, groups=3)  # 3 个模块，每块 2 个文件
    groups = sorted({u.group for u in pool})

    shared = BlindPartitioner(n_readers=3, redundancy=3, seed=0).partition(
        pool, round_index=0, focus_groups=groups[:1]
    )
    blind = BlindPartitioner(n_readers=3, redundancy=1, seed=0).partition(pool, round_index=0)

    def reads(parts) -> int:
        return sum(len(p.evidence_ids) for p in parts)

    def unique(parts) -> int:
        return len({e for p in parts for e in p.evidence_ids})

    assert reads(shared) == reads(blind), "两个实验臂的预算必须相同"
    assert unique(shared) == 2
    assert unique(blind) == 6
    assert unique(blind) == 3 * unique(shared), "分区式的唯一覆盖应是共享式的 n_readers 倍"


def test_focus_restricts_to_the_first_groups():
    """initial_focus_count 的实现基础：focus_groups 之外一条证据都不切。"""
    pool = units(n=6, groups=3)
    groups = sorted({u.group for u in pool})

    parts = BlindPartitioner(n_readers=2, redundancy=2, seed=0).partition(
        pool, round_index=0, focus_groups=groups[:1]
    )
    assert {u.group for p in parts for u in p.units} == {groups[0]}
