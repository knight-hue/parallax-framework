"""Verify dispatch against a temporary RabbitMQ using an existing cached image only."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", required=True, help="Existing local RabbitMQ 4.1+ image"
    )
    parser.add_argument("--maven", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    root = Path(__file__).resolve().parents[2]
    maven = args.maven.resolve(strict=True)
    java_home = args.java_home.resolve(strict=True)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def docker(*parts: str, check=True, timeout=20):
        return subprocess.run(
            ["docker", *parts],
            check=check,
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=timeout,
        )

    # Preflight before creating any resources. This tool never pulls or builds images.
    cached = docker("image", "inspect", args.image, check=False)
    if cached.returncode:
        print(
            "RabbitMQ gate unavailable: Docker engine or requested cached image is unavailable. No download attempted."
        )
        return 2
    image_id = json.loads(cached.stdout)[0]["Id"]
    name = "parallax-rabbit-it-" + secrets.token_hex(6)
    env = os.environ.copy()
    env["RABBITMQ_DEFAULT_USER"] = "parallax_test"
    env["RABBITMQ_DEFAULT_PASS"] = secrets.token_hex(24)
    created = False
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--pull=never",
                "--detach",
                "--name",
                name,
                "--hostname",
                name,
                "-e",
                "RABBITMQ_DEFAULT_USER",
                "-e",
                "RABBITMQ_DEFAULT_PASS",
                "-p",
                "127.0.0.1::5672",
                image_id,
            ],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=flags,
            timeout=30,
        )
        created = True
        port = json.loads(docker("inspect", name).stdout)[0]["NetworkSettings"][
            "Ports"
        ]["5672/tcp"][0]["HostPort"]
        # The management image needs roughly 25-40 s of a cold start on Windows containers,
        # so readiness must be a wall-clock deadline, not a fixed number of short polls.
        deadline = time.monotonic() + 180
        last_error = ""
        while time.monotonic() < deadline:
            try:
                probe = docker(
                    "exec",
                    "--user",
                    "rabbitmq",
                    name,
                    "rabbitmq-diagnostics",
                    "-q",
                    "check_running",
                    check=False,
                    timeout=10,
                )
                if probe.returncode == 0:
                    break
                last_error = (probe.stderr or probe.stdout or "").strip()[-400:]
            except subprocess.TimeoutExpired:
                last_error = "rabbitmq-diagnostics timed out"
            time.sleep(1.0)
        else:
            (output / "rabbit-failure.log").write_text(
                docker("logs", name, check=False).stdout
                + "\n--- inspect ---\n"
                + docker("inspect", name, check=False).stdout,
                encoding="utf-8",
            )
            raise RuntimeError(
                f"Temporary RabbitMQ did not become ready within 180 s: {last_error}"
            )
        test_env = os.environ.copy()
        for key in list(test_env):
            if key.startswith(("PARALLAX_", "OPENAI_", "SPRING_", "LOGGING_")):
                test_env.pop(key)
        test_env.update(
            JAVA_HOME=str(java_home),
            PARALLAX_TEST_RABBIT_ISOLATED="true",
            PARALLAX_TEST_RABBIT_URI=f"amqp://parallax_test:{env['RABBITMQ_DEFAULT_PASS']}@127.0.0.1:{port}/%2f",
        )
        with (output / "maven.log").open("wb") as log:
            result = subprocess.run(
                [
                    str(maven),
                    "-o",
                    "-B",
                    "-f",
                    str(root / "gateway/pom.xml"),
                    "verify",
                    "-DskipITs=false",
                    "-Dit.test=RabbitDispatchIT",
                    "-Dparallax.test.rabbit=true",
                ],
                cwd=root,
                env=test_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                timeout=600,
                check=False,
            )
        print(f"Real RabbitMQ gate exit={result.returncode}; logs={output}")
        return result.returncode
    finally:
        if created:
            docker("rm", "-f", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
