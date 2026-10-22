"""Deterministic 2PC/TCC simulations with independent SQLite resource stores.

These are protocol simulations, not a real XA coordinator or Seata. SQLite is used
to make prepare/commit/rollback and crash-recovery behavior reproducible without a
second database server. See README for the Seata boundary.
"""

from __future__ import annotations

import sqlite3
import tempfile
import uuid
from pathlib import Path


class Resource:
    def __init__(self, path: Path, initial: int = 10):
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            CREATE TABLE stock (id INTEGER PRIMARY KEY, quantity INTEGER NOT NULL);
            CREATE TABLE tcc (
                tx_id TEXT PRIMARY KEY,
                amount INTEGER NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('TRY','COMMITTED','CANCELED'))
            );
            """
        )
        self.connection.execute("INSERT INTO stock VALUES (1, ?)", (initial,))

    def try_reserve(self, tx_id: str, amount: int) -> bool:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT amount,state FROM tcc WHERE tx_id=?", (tx_id,)
            ).fetchone()
            if row is not None:
                self.connection.execute("COMMIT")
                return row[0] == amount and row[1] in ("TRY", "COMMITTED")
            quantity = self.connection.execute("SELECT quantity FROM stock WHERE id=1").fetchone()[0]
            if quantity < amount:
                self.connection.execute("ROLLBACK")
                return False
            self.connection.execute("UPDATE stock SET quantity=quantity-? WHERE id=1", (amount,))
            self.connection.execute(
                "INSERT INTO tcc (tx_id,amount,state) VALUES (?,?,'TRY')", (tx_id, amount)
            )
            self.connection.execute("COMMIT")
            return True
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def confirm(self, tx_id: str) -> None:
        row = self.connection.execute(
            "SELECT state FROM tcc WHERE tx_id=?", (tx_id,)
        ).fetchone()
        if row is None:
            raise AssertionError("confirm without try")
        if row[0] == "CANCELED":
            raise AssertionError("cannot confirm a canceled branch")
        if row[0] == "TRY":
            self.connection.execute(
                "UPDATE tcc SET state='COMMITTED' WHERE tx_id=? AND state='TRY'", (tx_id,)
            )

    def cancel(self, tx_id: str) -> bool:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT amount,state FROM tcc WHERE tx_id=?", (tx_id,)
            ).fetchone()
            if row is None:
                self.connection.execute("COMMIT")
                return False
            if row[1] == "COMMITTED":
                self.connection.execute("ROLLBACK")
                raise AssertionError("cannot cancel a committed branch")
            if row[1] == "TRY":
                self.connection.execute("UPDATE stock SET quantity=quantity+? WHERE id=1", (row[0],))
                self.connection.execute("UPDATE tcc SET state='CANCELED' WHERE tx_id=?", (tx_id,))
            self.connection.execute("COMMIT")
            return True
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def quantity(self) -> int:
        return self.connection.execute("SELECT quantity FROM stock WHERE id=1").fetchone()[0]

    def state(self, tx_id: str) -> str | None:
        row = self.connection.execute("SELECT state FROM tcc WHERE tx_id=?", (tx_id,)).fetchone()
        return None if row is None else row[0]

    def close(self) -> None:
        self.connection.close()


class Coordinator:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.execute(
            "CREATE TABLE tx_log (tx_id TEXT PRIMARY KEY, state TEXT NOT NULL)"
        )

    def begin(self, tx_id: str) -> None:
        self.connection.execute(
            "INSERT INTO tx_log (tx_id,state) VALUES (?,'PREPARING')", (tx_id,)
        )

    def decide(self, tx_id: str, state: str) -> None:
        if state not in ("COMMITTED", "ABORTED"):
            raise ValueError(state)
        self.connection.execute("UPDATE tx_log SET state=? WHERE tx_id=?", (state, tx_id))

    def recover(self, first: Resource, second: Resource) -> int:
        recovered = 0
        rows = self.connection.execute("SELECT tx_id,state FROM tx_log").fetchall()
        for tx_id, state in rows:
            if state == "PREPARING":
                self.connection.execute(
                    "UPDATE tx_log SET state='ABORTED' WHERE tx_id=?", (tx_id,)
                )
                first.cancel(tx_id)
                second.cancel(tx_id)
                recovered += 1
            elif state == "COMMITTED":
                first.confirm(tx_id)
                second.confirm(tx_id)
                recovered += 1
        return recovered

    def close(self) -> None:
        self.connection.close()


def setup(initial: int = 10):
    root = Path(tempfile.mkdtemp(prefix="parallax-2pc-"))
    first = Resource(root / "inventory.db", initial)
    second = Resource(root / "coupon.db", initial)
    coordinator = Coordinator(root / "coordinator.db")
    return first, second, coordinator


def two_phase_lab() -> None:
    print("== 2PC simulation ==")

    first, second, coordinator = setup()
    tx = uuid.uuid4().hex
    coordinator.begin(tx)
    assert first.try_reserve(tx, 2) and second.try_reserve(tx, 2)
    coordinator.decide(tx, "COMMITTED")
    first.confirm(tx)
    second.confirm(tx)
    first.confirm(tx)
    second.confirm(tx)
    print(f"commit: inventory={first.quantity()} coupon={second.quantity()} states="
          f"{first.state(tx)}/{second.state(tx)}")
    assert first.quantity() == 8 and second.quantity() == 8

    first.close(); second.close(); coordinator.close()

    first, second, coordinator = setup()
    tx = uuid.uuid4().hex
    coordinator.begin(tx)
    assert first.try_reserve(tx, 2)
    assert not second.try_reserve(tx, 99)
    coordinator.decide(tx, "ABORTED")
    first.cancel(tx)
    second.cancel(tx)
    print(f"prepare-failure abort: inventory={first.quantity()} coupon={second.quantity()}")
    assert first.quantity() == 10 and second.quantity() == 10

    first.close(); second.close(); coordinator.close()

    first, second, coordinator = setup()
    tx = uuid.uuid4().hex
    coordinator.begin(tx)
    assert first.try_reserve(tx, 2) and second.try_reserve(tx, 2)
    # Simulate a coordinator crash before writing a decision.
    recovered = coordinator.recover(first, second)
    print(f"crash-before-decision: recovered={recovered} inventory={first.quantity()} "
          f"coupon={second.quantity()}")
    assert recovered == 1 and first.quantity() == 10 and second.quantity() == 10

    first.close(); second.close(); coordinator.close()

    first, second, coordinator = setup()
    tx = uuid.uuid4().hex
    coordinator.begin(tx)
    assert first.try_reserve(tx, 2) and second.try_reserve(tx, 2)
    coordinator.decide(tx, "COMMITTED")
    # Simulate a crash after the durable commit decision but before branch commits.
    recovered = coordinator.recover(first, second)
    print(f"crash-after-decision: recovered={recovered} inventory={first.quantity()} "
          f"coupon={second.quantity()}")
    assert recovered == 1 and first.quantity() == 8 and second.quantity() == 8
    first.close(); second.close(); coordinator.close()


def tcc_lab() -> None:
    print("== TCC simulation ==")
    first, second, _ = setup()
    tx = uuid.uuid4().hex
    assert first.try_reserve(tx, 2) and second.try_reserve(tx, 2)
    first.confirm(tx); second.confirm(tx)
    first.confirm(tx); second.confirm(tx)
    print(f"confirm: inventory={first.quantity()} coupon={second.quantity()} states="
          f"{first.state(tx)}/{second.state(tx)}")
    assert first.quantity() == 8 and second.quantity() == 8

    tx = uuid.uuid4().hex
    assert first.try_reserve(tx, 3) and second.try_reserve(tx, 3)
    assert first.cancel(tx) and second.cancel(tx)
    assert first.cancel(tx) and second.cancel(tx)
    print(f"cancel/empty-rollback idempotent: inventory={first.quantity()} "
          f"coupon={second.quantity()} states={first.state(tx)}/{second.state(tx)}")
    assert first.quantity() == 8 and second.quantity() == 8

    # Hanging try is cancelled by timeout; no stock remains reserved.
    tx = uuid.uuid4().hex
    assert first.try_reserve(tx, 1)
    first.cancel(tx)
    print(f"hanging-prevention: inventory={first.quantity()} state={first.state(tx)}")
    assert first.quantity() == 8
    rejected = False
    try:
        first.confirm(tx)
    except AssertionError:
        rejected = True
    assert rejected
    print("confirm-after-cancel rejected as expected")
    first.close(); second.close()


def main() -> int:
    two_phase_lab()
    tcc_lab()
    print("distributed transaction labs completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
