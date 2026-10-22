"""Observable Redis encoding, cache failure modes and lock-expiry lab."""

from __future__ import annotations

import os
import random
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.resp import RedisError, Resp  # noqa: E402

HOST = os.environ.get("PARALLAX_LAB_REDIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("PARALLAX_LAB_REDIS_PORT", "6390"))
COMPARE_DELETE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


def client() -> Resp:
    return Resp(HOST, PORT)


def encoding_lab(redis: Resp) -> None:
    print("== Redis encoding ==")
    redis.cmd("SET", "enc:int", "123")
    redis.cmd("SET", "enc:short", "hello")
    redis.cmd("SET", "enc:long", "x" * 100)
    redis.cmd("HSET", "enc:hash", "a", "1", "b", "2")
    redis.cmd("SADD", "enc:set", "1", "2", "3")
    redis.cmd("ZADD", "enc:zset", "1", "a", "2", "b")
    for key in ("enc:int", "enc:short", "enc:long", "enc:hash", "enc:set", "enc:zset"):
        print(f"{key} encoding={redis.cmd('OBJECT', 'ENCODING', key)}")


def penetration_lab(redis: Resp) -> None:
    print("== cache penetration ==")
    calls = 0
    for _ in range(50):
        if redis.cmd("GET", "missing:plain") is None:
            calls += 1
    print(f"without negative cache: dbCalls={calls}")
    redis.cmd("SET", "missing:negative", "__NULL__", "EX", 30)
    avoided = 0
    for _ in range(50):
        if redis.cmd("GET", "missing:negative") == "__NULL__":
            avoided += 1
    print(f"with negative cache: dbCalls=0 hits={avoided}")


def breakdown_lab(redis: Resp) -> None:
    print("== cache breakdown / single-flight ==")
    redis.cmd("DEL", "cache:hot", "lock:hot")
    barrier = threading.Barrier(8)
    db_calls = 0
    counter_lock = threading.Lock()
    results: list[str | None] = []
    results_lock = threading.Lock()

    def worker() -> None:
        nonlocal db_calls
        local = client()
        try:
            barrier.wait()
            cached = local.cmd("GET", "cache:hot")
            if cached is not None:
                value: str | None = cached
            else:
                token = uuid.uuid4().hex
                if local.cmd("SET", "lock:hot", token, "NX", "PX", 2000) == "OK":
                    try:
                        cached = local.cmd("GET", "cache:hot")
                        if cached is not None:
                            value = cached
                        else:
                            with counter_lock:
                                db_calls += 1
                            time.sleep(0.2)
                            value = "payload"
                            local.cmd("SET", "cache:hot", value, "PX", 5000)
                    finally:
                        local.cmd("EVAL", COMPARE_DELETE, 1, "lock:hot", token)
                else:
                    deadline = time.time() + 2
                    value = None
                    while time.time() < deadline:
                        time.sleep(0.02)
                        cached = local.cmd("GET", "cache:hot")
                        if cached is not None:
                            value = cached
                            break
        finally:
            local.close()
        with results_lock:
            results.append(value)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    print(f"dbCalls={db_calls} readers={len(results)} allPayload={all(v == 'payload' for v in results)}")
    if db_calls != 1:
        raise AssertionError("single-flight lock should produce exactly one database load")


def avalanche_lab(redis: Resp) -> None:
    print("== TTL jitter ==")
    ttls = []
    for i in range(20):
        ttl_ms = random.randint(60_000, 90_000)
        redis.cmd("SET", f"jitter:{i}", "1", "PX", ttl_ms)
        ttls.append(redis.cmd("PTTL", f"jitter:{i}"))
    print(f"ttlMs min={min(ttls)} max={max(ttls)} spread={max(ttls) - min(ttls)}")


def lock_expiry_lab(redis: Resp) -> None:
    print("== lock expiry / compare-and-delete ==")
    redis.cmd("DEL", "lock:job")
    redis.cmd("SET", "lock:job", "old-holder", "NX", "PX", 50)
    time.sleep(0.1)
    redis.cmd("SET", "lock:job", "new-holder", "NX", "PX", 2000)
    deleted = redis.cmd("EVAL", COMPARE_DELETE, 1, "lock:job", "old-holder")
    current = redis.cmd("GET", "lock:job")
    print(f"oldHolderDelete={deleted} currentOwner={current}")
    if deleted != 0 or current != "new-holder":
        raise AssertionError("an expired holder must not delete the new owner's lock")


def failure_lab() -> None:
    print("== Redis unavailable ==")
    try:
        bad = Resp(HOST, 1, timeout=0.5)
        bad.close()
        raise AssertionError("port 1 should not accept Redis connections")
    except (OSError, RedisError) as exc:
        print(f"connection failed as expected: {type(exc).__name__}; caller must fall back to MySQL")


def main() -> int:
    with client() as redis:
        print(f"redis version={redis.cmd('INFO', 'server').splitlines()[1]}")
        redis.cmd("FLUSHDB")
        encoding_lab(redis)
        penetration_lab(redis)
        breakdown_lab(redis)
        avalanche_lab(redis)
        lock_expiry_lab(redis)
    failure_lab()
    print("redis lab completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
