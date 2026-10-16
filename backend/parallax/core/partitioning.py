"""盲读分区。

## 一个必须澄清的设计点：什么叫「不重叠」

《最终方案》原话是「N 个 Reader，每个只读**不重叠**的证据子集」。若严格照做
（每条证据只给 1 个 Reader），会出现一个致命的自相矛盾：

    没有任何两条 claim 来自同一个证据 → 交叉验证计数永远恒等于 1
    → 所有 claim 永远停在 PENDING → 「声誉加权聚合」机制直接失效

也就是说，**严格不重叠会让第 3 步机制变成死代码**。

所以这里把「不重叠」精确化为两条可验证的约束：

    ① 输出隔离（真正的抗从众约束）
       Reader 之间**永远看不到对方的 claim**。这条不能让步。
    ② 输入受控冗余（可调旋钮 redundancy）
       每条证据分给 redundancy 个 Reader。redundancy=1 即原方案的严格分区。

这个结构与 InfoDelphi 的「共享公开子集 + 互斥私有子集」完全同构，不是自创：
每个 Reader 既有别人也有的部分（可交叉验证），也有别人没有的部分（提供独立性）。

`redundancy` 因此成了本框架最重要的实验旋钮：

    redundancy 低  → 独立性高、交叉验证机会少（孤证多）
    redundancy 高  → 交叉验证多，但信息不对称减弱、从众风险回升

消融实验里这个旋钮的曲线，就是「独立性与可验证性的权衡」的直接证据。
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from parallax.domain.errors import ConfigurationError
from parallax.domain.models import EvidenceUnit


@dataclass(frozen=True)
class Partition:
    """一个 Reader 一轮看到的全部内容。"""

    reader_id: str
    round_index: int
    units: tuple[EvidenceUnit, ...]

    @property
    def evidence_ids(self) -> list[str]:
        return [u.evidence_id for u in self.units]

    @property
    def groups(self) -> list[str]:
        return sorted({u.group for u in self.units})


class BlindPartitioner:
    """确定性、分组感知的盲读分区器。

    分组感知的含义：同一个 group（代码审计里=同一个模块）尽量整体分给同一批
    Reader，而不是把文件劈成两半——让 Reader 读到残缺上下文会制造假缺陷。
    """

    def __init__(self, n_readers: int = 3, redundancy: int = 2, seed: int = 0) -> None:
        if n_readers < 1:
            raise ConfigurationError("n_readers 至少为 1")
        if redundancy < 1 or redundancy > n_readers:
            raise ConfigurationError(
                f"redundancy 必须落在 [1, n_readers] 内，当前 n_readers={n_readers} redundancy={redundancy}"
            )
        self.n_readers = n_readers
        self.redundancy = redundancy
        self.seed = seed

    def reader_ids(self, round_index: int) -> list[str]:
        """**每一轮生成全新的 Reader 身份**。

        这是「补检派新 Reader、而不是让老 Reader 补读」在代码上的体现：
        老 Reader 已经形成了结论，让它补读就是把从众请回来。
        """
        return [f"reader-r{round_index}-{i}" for i in range(self.n_readers)]

    def partition(
        self,
        units: list[EvidenceUnit],
        round_index: int,
        focus_groups: list[str] | None = None,
    ) -> list[Partition]:
        """切分证据。

        Args:
            units: 候选证据（通常来自 adapter）。
            round_index: 轮次，决定 Reader 身份与随机种子。
            focus_groups: 覆盖率监控点名的稀疏分组。给出时只切这些组的证据，
                实现对「未覆盖区域」的定向补检。
        """
        candidates = self._select(units, focus_groups)
        reader_ids = self.reader_ids(round_index)
        buckets: dict[str, list[EvidenceUnit]] = {rid: [] for rid in reader_ids}

        for group, group_units in self._by_group(candidates):
            offset = self._rotation_offset(group, round_index)
            for k in range(self.redundancy):
                rid = reader_ids[(offset + k) % self.n_readers]
                buckets[rid].extend(group_units)

        return [
            Partition(
                reader_id=rid,
                round_index=round_index,
                units=tuple(sorted(buckets[rid], key=lambda u: u.evidence_id)),
            )
            for rid in reader_ids
        ]

    # ---- 内部 ----

    @staticmethod
    def _select(units: list[EvidenceUnit], focus_groups: list[str] | None) -> list[EvidenceUnit]:
        if not focus_groups:
            return list(units)
        focus = set(focus_groups)
        return [u for u in units if u.group in focus]

    @staticmethod
    def _by_group(units: list[EvidenceUnit]) -> list[tuple[str, list[EvidenceUnit]]]:
        grouped: dict[str, list[EvidenceUnit]] = {}
        for unit in units:
            grouped.setdefault(unit.group, []).append(unit)
        return [(g, sorted(grouped[g], key=lambda u: u.evidence_id)) for g in sorted(grouped)]

    def _rotation_offset(self, group: str, round_index: int) -> int:
        """由 (seed, round_index, group) 派生起始 Reader 下标。

        用哈希而不是全局 RNG：这样某个分组的分到哪些 Reader 与遍历顺序无关，
        单测里可以直接断言，也不会因为新增一个分组而整体错位。
        """
        raw = f"{self.seed}:{round_index}:{group}".encode()
        digest = hashlib.sha1(raw).digest()
        return int.from_bytes(digest[:4], "big") % self.n_readers

    def redundancy_of(self, partitions: list[Partition]) -> dict[str, int]:
        """每条证据实际被多少个 Reader 分到——用于验证冗余旋钮是否生效。"""
        counts: dict[str, int] = {}
        for part in partitions:
            for eid in part.evidence_ids:
                counts[eid] = counts.get(eid, 0) + 1
        return counts

    def isolation_ok(self, partitions: list[Partition]) -> bool:
        """Reader 身份互不相同（输出隔离的前提）。"""
        ids = [p.reader_id for p in partitions]
        return len(ids) == len(set(ids))


def shuffled_copy(units: list[EvidenceUnit], seed: int) -> list[EvidenceUnit]:
    """保留的调试助手：需要观察顺序敏感性时用。"""
    out = list(units)
    random.Random(seed).shuffle(out)
    return out
