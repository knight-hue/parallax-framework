"""Flash-sale lab: SQLite conditional decrement baseline vs Redis Lua pre-deduction."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.resp import Resp  # noqa: E402

HOST = os.environ.get("PARALLAX_LAB_REDIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("PARALLAX_LAB_REDIS_PORT", "6390"))
INITIAL = 100
ATTEMPTS = 200
LUA = """
local granted = redis.call('set', KEYS[2], '1', 'NX', 'EX', 60)
if not granted then return -1 end
local stock = tonumber(redis.call('get', KEYS[1]) or '0')
if stock <= 0 then
  redis.call('del', KEYS[2])
  return 0
end
redis.call('decr', KEYS[1])
return 1
"""


def reset_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            DROP TABLE IF EXISTS stock;
            DROP TABLE IF EXISTS orders;
            CREATE TABLE stock (id INTEGER PRIMARY KEY, quantity INTEGER NOT NULL);
            CREATE TABLE orders (user_id TEXT PRIMARY KEY, at TEXT NOT NULL);
            INSERT INTO stock (id, quantity) VALUES (1, 100);
            """
        )


def sqlite_attempt(path: Path, user: str) -> bool:
    with sqlite3.connect(path, timeout=30, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE stock SET quantity=quantity-1 WHERE id=1 AND quantity>0"
        ).rowcount
        if changed == 1:
            db.execute("INSERT OR IGNORE INTO orders (user_id, at) VALUES (?, datetime('now'))", (user,))
            db.execute("COMMIT")
            return True
        db.execute("COMMIT")
        return False


def sqlite_baseline(path: Path) -> int:
    successes = 0
    lock = threading.Lock()

    def worker(user: str) -> None:
        nonlocal successes
        if sqlite_attempt(path, user):
            with lock:
                successes += 1

    threads = [threading.Thread(target=worker, args=(f"user-{i}",)) for i in range(ATTEMPTS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    with sqlite3.connect(path) as db:
        quantity = db.execute("SELECT quantity FROM stock WHERE id=1").fetchone()[0]
        orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"sqlite baseline: successes={successes} stock={quantity} orders={orders}")
    if successes != INITIAL or quantity != 0 or orders != INITIAL:
        raise AssertionError("SQLite conditional decrement oversold or lost orders")
    return successes


def run_attempts(users: list[str]) -> tuple[list[str], dict[int, int]]:
    successes: list[str] = []
    counts = {1: 0, 0: 0, -1: 0}
    lock = threading.Lock()

    def worker(user: str) -> None:
        local = Resp(HOST, PORT)
        try:
            result = int(local.cmd("EVAL", LUA, 2, "flash:stock", f"flash:user:{user}"))
        finally:
            local.close()
        with lock:
            counts[result] += 1
            if result == 1:
                successes.append(user)

    threads = [threading.Thread(target=worker, args=(user,)) for user in users]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    return successes, counts


def redis_pre_deduct() -> list[str]:
    redis = Resp(HOST, PORT)
    try:
        redis.cmd("FLUSHDB")
        redis.cmd("SET", "flash:stock", INITIAL)
        first, first_counts = run_attempts([f"user-{i}" for i in range(INITIAL)])
        repeated, repeat_counts = run_attempts([f"user-{i}" for i in range(INITIAL)])
        sold_out, sold_counts = run_attempts([f"extra-{i}" for i in range(INITIAL)])
        stock = int(redis.cmd("GET", "flash:stock"))
        print(f"redis pre-deduct: firstSuccess={first_counts[1]} "
              f"repeatDuplicate={repeat_counts[-1]} soldOut={sold_counts[0]} stock={stock}")
        if first_counts[1] != INITIAL or repeat_counts[-1] != INITIAL or sold_counts[0] != INITIAL:
            raise AssertionError("Redis pre-deduction did not observe all expected outcomes")
        if stock != 0 or repeated or sold_out:
            raise AssertionError("Redis pre-deduction oversold or granted a duplicate")
        return first
    finally:
        redis.close()


def confirm_orders(path: Path, users: list[str]) -> None:
    with sqlite3.connect(path) as db:
        db.executemany(
            "INSERT OR IGNORE INTO orders (user_id, at) VALUES (?, datetime('now'))",
            [(user,) for user in users],
        )
        db.commit()
        orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"async confirmation: orders={orders}")
    if orders != INITIAL:
        raise AssertionError("confirmed orders do not match the granted quantity")


def main() -> int:
    path = Path(tempfile.gettempdir()) / "parallax-flash-sale.sqlite3"
    reset_db(path)
    sqlite_baseline(path)
    reset_db(path)
    successes = redis_pre_deduct()
    confirm_orders(path, successes)
    print("flash-sale lab completed: no oversell, no duplicate order, reconciled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
