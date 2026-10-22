"""Control-plane load probe against one or more gateway instances.

Measures latency percentiles, error rate and throughput for an authenticated read endpoint.
Uses only the standard library so it runs in the existing backend virtualenv.
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def percentile(samples: list[float], fraction: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def call(base: str, path: str, api_key: str, timeout: float) -> tuple[int, float]:
    request = urllib.request.Request(base.rstrip("/") + path, headers={"X-API-Key": api_key})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        error.read()
        status = error.code
    except Exception:  # noqa: BLE001 - network failures are data for the probe
        status = -1
    return status, (time.perf_counter() - started) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, action="append", help="instance base URL, repeatable")
    parser.add_argument("--path", default="/api/v1/usage/me")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--requests", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    instances = args.base
    latencies: list[float] = []
    statuses: dict[int, int] = {}
    lock = threading.Lock()
    counter = {"next": 0}

    def worker(_: int) -> None:
        with lock:
            index = counter["next"]
            counter["next"] += 1
        base = instances[index % len(instances)]
        status, elapsed = call(base, args.path, args.api_key, args.timeout)
        with lock:
            latencies.append(elapsed)
            statuses[status] = statuses.get(status, 0) + 1

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(worker, range(args.requests)))
    wall = time.perf_counter() - started

    ok = statuses.get(200, 0)
    report = {
        "instances": instances,
        "path": args.path,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "wall_seconds": round(wall, 3),
        "throughput_rps": round(args.requests / wall, 2) if wall else 0.0,
        "status_counts": {str(key): value for key, value in sorted(statuses.items())},
        "success": ok,
        "error_rate": round(1 - ok / args.requests, 4),
        "latency_ms": {
            "min": round(min(latencies), 2),
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "max": round(max(latencies), 2),
            "mean": round(statistics.fmean(latencies), 2),
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "capacity.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"rps={report['throughput_rps']} p50={report['latency_ms']['p50']}ms "
        f"p95={report['latency_ms']['p95']}ms p99={report['latency_ms']['p99']}ms "
        f"error_rate={report['error_rate']}"
    )
    return 0 if ok == args.requests else 1


if __name__ == "__main__":
    raise SystemExit(main())
