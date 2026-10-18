"""声誉：存储与更新策略。

## 「异见者不受惩罚」——本项目最反直觉、也最重要的一条规则

直觉做法是用「少数服从多数」更新 Agent 声誉：跟多数一致就加分，唱反调就扣分。
**但这本身就是一种从众压力**——Agent 会迅速学会「不要第一个说不同意见」，
于是我们在框架内部亲手重建了我们想消灭的那件事。

因此本实现规定：

    交叉验证通过        → 所有主张者 +1 verified
    孤证 (PENDING)      → 不更新（既未被验证也未被否证，不携带信息）
    争议 (DISPUTED)     → **不更新，双方都不动**（等仲裁，不预先惩罚少数方）
    仲裁裁决后          → 胜方 arbitration_win，败方 arbitration_loss

声誉分用 Beta 后验均值：score = (1 + 命中) / (2 + 命中 + 未命中)
新 Agent 从 0.5 中性起步，样本少时不会暴涨，无需调参，可解释。
"""

from __future__ import annotations

import json
import sqlite3
from collections import OrderedDict
from pathlib import Path

from parallax.core.ledger import ClaimLedger, LedgerGroup
from parallax.domain.enums import ClaimStatus, Polarity
from parallax.domain.models import AgentReputation
from parallax.ports.stores import ReputationStore


class InMemoryReputationStore:
    """内存实现，用于开发与测试。

    生产替换为 Redis/Postgres 实现即可——`ReputationStore` 协议已经定死了三个方法，
    上层不感知具体存储。
    """

    def __init__(self) -> None:
        self._reps: OrderedDict[str, AgentReputation] = OrderedDict()

    def get(self, agent_id: str, role: str = "reader") -> AgentReputation:
        rep = self._reps.get(agent_id)
        if rep is None:
            rep = AgentReputation(agent_id=agent_id, role=role)
            self._reps[agent_id] = rep
        return rep

    def save(self, reputation: AgentReputation) -> None:
        self._reps[reputation.agent_id] = reputation

    def all(self) -> list[AgentReputation]:
        return list(self._reps.values())

    def scores(self) -> dict[str, float]:
        """给评测用的快照：agent_id -> 声誉分。"""
        return {r.agent_id: round(r.score(), 4) for r in self._reps.values()}

    def record_event(
        self,
        agent_id: str,
        run_id: str,
        claim_id: str,
        outcome: str,
        role: str = "reader",
    ) -> AgentReputation:
        reputation = self.get(agent_id, role=role)
        reputation.record(run_id=run_id, claim_id=claim_id, outcome=outcome)
        self.save(reputation)
        return reputation


class SQLiteReputationStore:
    """跨进程持久化的声誉存储。

    SQLite 适合单机或共享文件卷上的轻量部署：每次更新都在短事务中完成，
    进程重启不会丢失历史，且不需要为核心服务额外引入 Redis/Postgres。
    高并发多副本部署仍可把同一协议替换为平台数据库实现。
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_reputation (
                    agent_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    claims_verified INTEGER NOT NULL DEFAULT 0,
                    claims_refuted INTEGER NOT NULL DEFAULT 0,
                    arbitration_wins INTEGER NOT NULL DEFAULT 0,
                    arbitration_losses INTEGER NOT NULL DEFAULT 0,
                    events_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    @staticmethod
    def _from_row(row: sqlite3.Row) -> AgentReputation:
        return AgentReputation(
            agent_id=row["agent_id"],
            role=row["role"],
            claims_verified=row["claims_verified"],
            claims_refuted=row["claims_refuted"],
            arbitration_wins=row["arbitration_wins"],
            arbitration_losses=row["arbitration_losses"],
            events=json.loads(row["events_json"]),
        )

    def get(self, agent_id: str, role: str = "reader") -> AgentReputation:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_reputation WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if row is None:
                reputation = AgentReputation(agent_id=agent_id, role=role)
                self.save(reputation)
                return reputation
            return self._from_row(row)

    def save(self, reputation: AgentReputation) -> None:
        events = [event.model_dump(mode="json") for event in reputation.events]
        with self._connect() as conn:
            self._save_connection(conn, reputation, events)

    @staticmethod
    def _save_connection(
        conn: sqlite3.Connection,
        reputation: AgentReputation,
        events: list[dict],
    ) -> None:
        conn.execute(
            """
            INSERT INTO agent_reputation
                (agent_id, role, claims_verified, claims_refuted,
                 arbitration_wins, arbitration_losses, events_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                role=excluded.role,
                claims_verified=excluded.claims_verified,
                claims_refuted=excluded.claims_refuted,
                arbitration_wins=excluded.arbitration_wins,
                arbitration_losses=excluded.arbitration_losses,
                events_json=excluded.events_json
            """,
            (
                reputation.agent_id,
                reputation.role,
                reputation.claims_verified,
                reputation.claims_refuted,
                reputation.arbitration_wins,
                reputation.arbitration_losses,
                json.dumps(events, ensure_ascii=False, sort_keys=True),
            ),
        )

    def record_event(
        self,
        agent_id: str,
        run_id: str,
        claim_id: str,
        outcome: str,
        role: str = "reader",
    ) -> AgentReputation:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM agent_reputation WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            reputation = (
                self._from_row(row)
                if row is not None
                else AgentReputation(agent_id=agent_id, role=role)
            )
            reputation.record(run_id=run_id, claim_id=claim_id, outcome=outcome)
            self._save_connection(
                conn,
                reputation,
                [event.model_dump(mode="json") for event in reputation.events],
            )
            return reputation

    def all(self) -> list[AgentReputation]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agent_reputation ORDER BY agent_id").fetchall()
        return [self._from_row(row) for row in rows]

    def scores(self) -> dict[str, float]:
        return {item.agent_id: round(item.score(), 4) for item in self.all()}


class ReputationPolicy:
    """把聚合结论转成声誉变动。"""

    def __init__(self, store: ReputationStore) -> None:
        self.store = store

    def _record(self, agent_id: str, run_id: str, claim_id: str, outcome: str) -> AgentReputation:
        return self.store.record_event(agent_id, run_id, claim_id, outcome)

    def apply_cross_validation(
        self,
        groups: list[LedgerGroup],
        ledger: ClaimLedger,
        run_id: str,
    ) -> dict[str, float]:
        """按高置信结论给主张者记 verified。

        返回本次变动的 agent -> 分数，便于实验报告展示。
        """
        updated: dict[str, float] = {}
        for group in groups:
            if group.status != ClaimStatus.HIGH_CONFIDENCE:
                # PENDING / DISPUTED 都不更新，理由见模块 docstring
                continue
            for claim_id in group.claim_ids:
                claim = ledger.claim(claim_id)
                if claim is None:
                    continue
                rep = self._record(claim.extracted_by, run_id, claim_id, "verified")
                updated[claim.extracted_by] = round(rep.score(), 4)
        return updated

    def apply_arbitration(
        self,
        group: LedgerGroup,
        ledger: ClaimLedger,
        run_id: str,
        upheld: ClaimStatus,
    ) -> dict[str, float]:
        """仲裁裁决落地后才结算声誉。

        裁决为 HIGH_CONFIDENCE → ASSERT 方胜；裁决为 PENDING → 视为未能证实，
        DENY 方胜（「无法证实」不等于「证伪」，所以只做 win/loss 记录，不改 claim 结论语义）。
        """
        winners_polarity = (
            Polarity.ASSERT if upheld == ClaimStatus.HIGH_CONFIDENCE else Polarity.DENY
        )
        updated: dict[str, float] = {}
        for claim_id in group.claim_ids:
            claim = ledger.claim(claim_id)
            if claim is None:
                continue
            outcome = (
                "arbitration_win" if claim.polarity == winners_polarity else "arbitration_loss"
            )
            rep = self._record(claim.extracted_by, run_id, claim_id, outcome)
            updated[claim.extracted_by] = round(rep.score(), 4)
        return updated
