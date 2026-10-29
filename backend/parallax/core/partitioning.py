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
import math
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

    ## 但分组必须设上限（真实仓库逼出来的修正）

    「同组整体分配」在**模块大小不均**时会退化。实测 anyio（46 文件 / 5 模块 /
    最大模块 18）在 R=3、K=2 下，三个 Reader 拿到的文件数是 33 / 38 / 21——
    前两个读了 72%~83% 的全部文件，盲读失去意义，而这种退化**看起来像"从众"**，
    实际是分区不均衡造成的假象。

    修正是给分组设一个单元数上限 `ceil(N / R)`，超过就切成连续块：
    块沿用同一个 `group` 标签（覆盖率矩阵的行不变），但旋转下标加上块序号，
    于是同组各块分给不同 Reader，负载回到理论值附近（K=2、R=3 时约 67%）。

    上限取 `ceil(N / R)` 而不是更小的值，是为了**不改变结构均匀的语料**：
    seed_c 是 6 个模块各 8 个文件，R=6 时上限恰好为 8，不触发切块，
    因此此前发布的实验结果仍然成立。
    """

    def __init__(
        self,
        n_readers: int = 3,
        redundancy: int = 2,
        seed: int = 0,
        max_units_per_group: int = 0,
        assignment: str = "hash",
    ) -> None:
        if n_readers < 1:
            raise ConfigurationError("n_readers 至少为 1")
        if redundancy < 1 or redundancy > n_readers:
            raise ConfigurationError(
                f"redundancy 必须落在 [1, n_readers] 内，当前 n_readers={n_readers} redundancy={redundancy}"
            )
        if assignment not in {"hash", "greedy"}:
            raise ConfigurationError("assignment 只能是 'hash' 或 'greedy'")
        self.n_readers = n_readers
        self.redundancy = redundancy
        self.seed = seed
        self.max_units_per_group = max_units_per_group
        """0 = 自动（ceil(N / n_readers)）。显式给值可覆盖，便于实验对比。"""
        self.assignment = assignment
        """分组到 Reader 的分配算法。

        `hash`（默认）：按 `(seed, round, group)` 的哈希旋转，等价于旧行为。
        `greedy`：按块大小降序贪心装到当前负载最低的 Reader，使各 Reader 条数近似相等。
        """

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

        chunks = self._chunked_groups(candidates)
        if self.assignment == "greedy":
            self._assign_greedy(chunks, reader_ids, buckets)
        else:
            for group, group_units, chunk_index in chunks:
                # 块序号参与旋转：否则同组的各块会分给同一批 Reader，切块就白做了。
                # 未切块的组 chunk_index 恒为 0，旋转结果与旧实现完全一致。
                offset = (self._rotation_offset(group, round_index) + chunk_index) % self.n_readers
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

    def _group_cap(self, total_units: int) -> int:
        """单个分组的单元数上限。"""
        if self.max_units_per_group > 0:
            return self.max_units_per_group
        return max(1, math.ceil(total_units / self.n_readers))

    def _chunked_groups(
        self, units: list[EvidenceUnit]
    ) -> list[tuple[str, list[EvidenceUnit], int]]:
        """把过大的分组切成连续块。

        返回 `(group, units, chunk_index)`。`chunk_index` 在同一组内从 0 递增，
        未切块时为 0——这保证了与旧实现的行为兼容。
        """
        cap = self._group_cap(len(units))
        out: list[tuple[str, list[EvidenceUnit], int]] = []
        for group, group_units in self._by_group(units):
            if len(group_units) <= cap:
                out.append((group, group_units, 0))
                continue
            n_chunks = math.ceil(len(group_units) / cap)
            # 均分而不是"前 n-1 块满、最后一块剩"：后者会给末块极小的负载，
            # 让该块的 Reader 几近空跑。
            base, extra = divmod(len(group_units), n_chunks)
            cursor = 0
            for i in range(n_chunks):
                size = base + (1 if i < extra else 0)
                out.append((group, group_units[cursor : cursor + size], i))
                cursor += size
        return out

    def _assign_greedy(
        self,
        chunks: list[tuple[str, list[EvidenceUnit], int]],
        reader_ids: list[str],
        buckets: dict[str, list[EvidenceUnit]],
    ) -> None:
        """按负载贪心分配，使每个 Reader 的条数尽量相等。

        ## 为什么需要这个模式（实测事故）

        按组哈希轮转在**组数少**时会严重失衡。各切片在 `group_depth=2` 下只有
        4~5 个分组，而真实项目的分组大小天然不均，于是 3 个 Reader 分 4 个组时
        必然撞车。实测最坏情况（S4 深度 3）出现 `1 / 25 / 0`——一个 Reader 空转，
        两个 Reader 负载差 25 倍。这种分布下「每个 Reader 预算相同」根本不成立，
        「集中 vs 分散」的受控对比也就失去了意义（差异会被分区不均讲圆）。

        ## 默认仍是 hash

        `hash` 唯一对应旧行为，已发布的实验结果不受影响；`greedy` 是需要均衡
        分配时的**显式选择**。分配过程完全确定：块按条数降序（同条数按分组名、
        块序号），Reader 按负载升序（同负载按下标），因此可复现、可重算。
        """
        ordered = sorted(chunks, key=lambda c: (-len(c[1]), c[0], c[2]))
        loads: dict[str, int] = dict.fromkeys(reader_ids, 0)
        for _group, group_units, _chunk_index in ordered:
            targets = sorted(reader_ids, key=lambda rid: (loads[rid], rid))[: self.redundancy]
            for rid in targets:
                buckets[rid].extend(group_units)
                loads[rid] += len(group_units)

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
