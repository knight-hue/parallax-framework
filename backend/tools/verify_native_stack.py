"""Verify built web -> authenticated Java -> Python -> PG/Redis on loopback.

Uses only local binaries/images, deterministic fake model, unique disposable
containers and child processes. This does not deploy a public TLS endpoint.
Run from backend after frontend build and offline Maven package.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_http(url, processes, timeout=150):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("A smoke-test process exited; inspect its local log")
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Service did not become ready at {url}")


def run(args):
    backend = Path(__file__).resolve().parents[1]
    repo = backend.parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    docker = shutil.which("docker")
    java = repo / ".toolchain/jdk/bin/java.exe"
    node = repo / ".toolchain/node/node.exe"
    if not java.exists():
        java = Path(shutil.which("java") or "missing-java")
    if not node.exists():
        node = Path(shutil.which("node") or "missing-node")
    jar = repo / "gateway/target/parallax-gateway-0.1.0.jar"
    web = repo / "frontend/.next/standalone/server.js"
    if not docker or not all(p.is_file() for p in (java, node, jar, web)):
        raise RuntimeError(
            "Required local tools/production artifacts are missing; nothing downloaded"
        )
    for image in (args.postgres_image, args.redis_image):
        subprocess.run([docker, "image", "inspect", image], check=True, stdout=subprocess.DEVNULL)
    api_port, gateway_port, web_port, pg_port, redis_port = [port() for _ in range(5)]
    suffix = uuid.uuid4().hex[:12]
    containers = [f"parallax-smoke-pg-{suffix}", f"parallax-smoke-redis-{suffix}"]
    processes, logs = [], []
    secret = secrets.token_hex(24)
    env = dict(os.environ)
    env.update(POSTGRES_PASSWORD=secret, POSTGRES_USER="parallax", POSTGRES_DB="parallax")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def start(argv, name, process_env, cwd):
        log = (out / f"{name}.log").open("wb")
        logs.append(log)
        process = subprocess.Popen(
            [str(v) for v in argv],
            cwd=cwd,
            env=process_env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        processes.append(process)
        return process

    def request(method, url, expected=200, **kwargs):
        response = httpx.request(method, url, timeout=30, **kwargs)
        if response.status_code != expected:
            raise RuntimeError(
                f"{method} {response.request.url.path}: HTTP {response.status_code}, expected {expected}"
            )
        return response

    checks = []
    try:
        subprocess.run(
            [
                docker,
                "run",
                "--pull=never",
                "-d",
                "--rm",
                "--name",
                containers[0],
                "-p",
                f"127.0.0.1:{pg_port}:5432",
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_USER",
                "-e",
                "POSTGRES_DB",
                args.postgres_image,
            ],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                docker,
                "run",
                "--pull=never",
                "-d",
                "--rm",
                "--name",
                containers[1],
                "-p",
                f"127.0.0.1:{redis_port}:6379",
                args.redis_image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        for _ in range(120):
            ready = (
                subprocess.run(
                    [docker, "exec", containers[0], "pg_isready", "-U", "parallax"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )
            if ready:
                break
            time.sleep(0.25)
        if not ready:
            raise RuntimeError("Cached PostgreSQL did not become ready")
        source = out / "source"
        source.mkdir()
        (source / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        native_env = dict(env)
        native_env.update(
            PARALLAX_GATEWAY_INTERNAL_TOKEN=secret,
            PARALLAX_AUDIT_ROOT=str(source),
            PARALLAX_RUNS_DIR=str(out / "runs"),
            PARALLAX_CALLBACK_URL=f"http://127.0.0.1:{gateway_port}",
            PARALLAX_CALLBACK_TOKEN=secret,
            PARALLAX_LLM_API_KEY="offline-smoke-fixture",
            PARALLAX_LLM_BASE_URL="http://127.0.0.1:1/v1",
            PARALLAX_LLM_MODEL="deterministic-fixture",
            PARALLAX_N_READERS="1",
            PARALLAX_REDUNDANCY="1",
            PARALLAX_MAX_ROUNDS="1",
            PARALLAX_ENABLE_LLM_FALSIFIER="false",
            PARALLAX_ENABLE_REPRODUCTION="false",
            PARALLAX_ENABLE_REPAIR="false",
            PARALLAX_CORS_ORIGINS="[]",
        )
        bootstrap = (
            "import uvicorn; from parallax.config import Settings; "
            "from parallax.service.app import create_app; from parallax.infra.llm_fake import FakeLLMClient; "
            "app=create_app(Settings(_env_file=None),client_factory=lambda _:FakeLLMClient(lambda _: {'findings':[]})); "
            f"uvicorn.run(app,host='127.0.0.1',port={api_port})"
        )
        start([sys.executable, "-c", bootstrap], "api", native_env, backend)
        wait_http(f"http://127.0.0.1:{api_port}/health", processes)
        gateway_env = dict(env)
        gateway_env.update(
            PARALLAX_GATEWAY_PORT=str(gateway_port),
            PARALLAX_GATEWAY_REQUIRE_AUTH="true",
            PARALLAX_GATEWAY_ADMIN_SECRET=secret,
            PARALLAX_GATEWAY_INTERNAL_TOKEN=secret,
            PARALLAX_JWT_SECRET=secret,
            PARALLAX_IDENTITY_ENABLED="true",
            PARALLAX_DB_URL=f"jdbc:postgresql://127.0.0.1:{pg_port}/parallax",
            SPRING_PROFILES_ACTIVE="legacy-postgres",
            PARALLAX_DB_USER="parallax",
            PARALLAX_DB_PASSWORD=secret,
            PARALLAX_UPSTREAM_URL=f"http://127.0.0.1:{api_port}",
            PARALLAX_RATELIMIT_REDIS_URL=f"redis://127.0.0.1:{redis_port}",
        )
        start([java, "-jar", jar, "--server.address=127.0.0.1"], "gateway", gateway_env, repo)
        gateway_url = f"http://127.0.0.1:{gateway_port}"
        wait_http(gateway_url + "/actuator/health/liveness", processes)
        web_env = dict(env)
        web_env.update(
            PORT=str(web_port),
            HOSTNAME="127.0.0.1",
            NEXT_TELEMETRY_DISABLED="1",
            PARALLAX_SERVER_API=gateway_url,
        )
        start([node, web], "web", web_env, web.parent)
        base = f"http://127.0.0.1:{web_port}"
        wait_http(base, processes)
        checks.append("built_web_gateway_python_started")
        request("GET", base + "/backend/api/v1/meta", expected=401)
        request("GET", f"http://127.0.0.1:{api_port}/api/v1/meta", expected=401)
        checks.append("anonymous_and_direct_api_denied")
        token = request("POST", gateway_url + "/api/v1/auth/token", json={"secret": secret}).json()[
            "accessToken"
        ]
        admin = {"Authorization": "Bearer " + token}
        key = request(
            "POST",
            gateway_url + "/api/v1/credentials",
            headers=admin,
            json={"name": "native-smoke"},
        ).json()["apiKey"]
        headers = {"X-API-Key": key}
        request("GET", base + "/backend/api/v1/meta", headers=headers)
        run_id = request(
            "POST",
            base + "/backend/api/v1/audits",
            expected=202,
            headers=headers,
            json={"repo_path": str(source), "readers": 1, "redundancy": 1, "max_rounds": 1},
        ).json()["run_id"]
        events = request(
            "GET", base + f"/backend/api/v1/audits/{run_id}/events", headers=headers
        ).text
        if "event: done" not in events:
            raise RuntimeError("SSE did not deliver terminal event")
        ids = [int(line[4:].strip()) for line in events.splitlines() if line.startswith("id: ")]
        if not ids:
            raise RuntimeError("SSE has no replay IDs")
        replay_headers = {**headers, "Last-Event-ID": str(ids[-1])}
        replay = request(
            "GET", base + f"/backend/api/v1/audits/{run_id}/events", headers=replay_headers
        )
        if "data:" in replay.text:
            raise RuntimeError("SSE replay repeated events already acknowledged")
        checks.append("authenticated_submission_sse_and_replay_through_web")
        result = request(
            "GET", base + f"/backend/api/v1/audits/{run_id}/result", headers=headers
        ).json()
        if not result.get("ready") or result["status"] != "done":
            raise RuntimeError("Audit result not persisted")
        request("GET", base + f"/backend/api/v1/audits/{run_id}/receipts", headers=headers)
        request(
            "POST",
            base + f"/backend/api/v1/audits/{run_id}/repairs",
            expected=403,
            headers=headers,
            json={"claim_id": "not-used"},
        )
        checks.append("results_receipts_and_repair_authorization")
        for _ in range(100):
            records = request("GET", gateway_url + "/api/v1/runs?status=done", headers=admin).json()
            if any(item.get("runId") == run_id for item in records.get("items", [])):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Real completion callback did not finalize the PostgreSQL run")
        checks.append("postgres_flyway_identity_and_completion_callback")
        metrics = request("GET", gateway_url + "/actuator/prometheus", headers=admin).text
        if "parallax" not in metrics:
            raise RuntimeError("Gateway metrics missing")
        checks.append("authenticated_metrics_with_redis_configured")
        (out / "acceptance.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "checks": checks,
                    "model_mode": "deterministic_fake_no_model_network",
                    "public_deployment": False,
                    "postgres_image": args.postgres_image,
                    "redis_image": args.redis_image,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(json.dumps({"passed": True, "checks": checks}, indent=2), flush=True)
        return 0
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in logs:
            log.close()
        for container in containers:
            subprocess.run(
                [docker, "rm", "-f", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--postgres-image", required=True)
    parser.add_argument("--redis-image", required=True)
    raise SystemExit(run(parser.parse_args()))
