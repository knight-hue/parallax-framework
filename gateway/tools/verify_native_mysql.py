"""Run real MySQL verification using an existing installation, never the user's data directory."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def postgres_source(image: str | None, password: str, flags: int):
    if not image:
        yield None
        return
    name = "parallax-transfer-" + secrets.token_hex(6)
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = password
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--pull=never",
                "--rm",
                "--detach",
                "--name",
                name,
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_USER=parallax_test",
                "-e",
                "POSTGRES_DB=source",
                "-p",
                "127.0.0.1::5432",
                image,
            ],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=flags,
            timeout=30,
        )
        details = subprocess.run(
            ["docker", "inspect", name],
            check=True,
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=10,
        )
        port = json.loads(details.stdout)[0]["NetworkSettings"]["Ports"]["5432/tcp"][0][
            "HostPort"
        ]
        for _ in range(100):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-U",
                    "parallax_test",
                    "-d",
                    "source",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                timeout=3,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Temporary PostgreSQL did not become ready")
        yield f"jdbc:postgresql://127.0.0.1:{port}/source"
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            timeout=20,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysql-home", type=Path, required=True)
    parser.add_argument("--maven", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--postgres-image",
        help="Existing cached image for real PostgreSQL-to-MySQL transfer",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    home = args.mysql_home.resolve(strict=True)
    suffix = ".exe" if os.name == "nt" else ""
    server, client = (
        home / "bin" / ("mysqld" + suffix),
        home / "bin" / ("mysql" + suffix),
    )
    if not server.is_file() or not client.is_file():
        parser.error("Existing mysqld and mysql binaries are required")
    maven = args.maven.resolve(strict=True)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    root_password, password = secrets.token_hex(24), secrets.token_hex(24)
    with (
        postgres_source(args.postgres_image, password, flags) as source_url,
        tempfile.TemporaryDirectory(prefix="parallax-mysql-") as temporary,
    ):
        data = Path(temporary) / "data"
        log = output / "mysql-server.log"
        with log.open("wb") as stream:
            base = [
                str(server),
                "--no-defaults",
                f"--basedir={home.as_posix()}",
                f"--datadir={data.as_posix()}",
            ]
            initialized = subprocess.run(
                base + ["--initialize-insecure", "--console"],
                check=False,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                timeout=90,
            )
            if initialized.returncode:
                raise RuntimeError(
                    "Temporary MySQL initialization failed; inspect server log"
                )
            process = subprocess.Popen(
                base
                + [
                    "--console",
                    "--bind-address=127.0.0.1",
                    f"--port={port}",
                    "--mysqlx=0",
                    "--skip-log-bin",
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            try:
                command = [
                    str(client),
                    "--no-defaults",
                    "--protocol=TCP",
                    "--host=127.0.0.1",
                    f"--port={port}",
                    "--user=root",
                    "--batch",
                ]
                ready = False
                for _ in range(150):
                    if process.poll() is not None:
                        raise RuntimeError("Temporary MySQL exited; inspect server log")
                    probe_result = subprocess.run(
                        command,
                        check=False,
                        input="SELECT 1;",
                        text=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=flags,
                        timeout=3,
                    )
                    if probe_result.returncode == 0:
                        ready = True
                        break
                    time.sleep(0.2)
                if not ready:
                    raise RuntimeError("Temporary MySQL did not become ready")
                sql = f"CREATE DATABASE parallax_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin; CREATE DATABASE parallax_transfer CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin; CREATE USER 'parallax_test'@'127.0.0.1' IDENTIFIED BY '{password}'; GRANT ALL ON parallax_test.* TO 'parallax_test'@'127.0.0.1'; GRANT ALL ON parallax_transfer.* TO 'parallax_test'@'127.0.0.1'; ALTER USER 'root'@'localhost' IDENTIFIED BY '{root_password}';"
                subprocess.run(
                    command,
                    input=sql,
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    check=True,
                    creationflags=flags,
                    timeout=10,
                )
                env = os.environ.copy()
                env.update(
                    JAVA_HOME=str(args.java_home.resolve(strict=True)),
                    PARALLAX_TEST_DB_PASSWORD=password,
                )
                # Do not inherit user model credentials or Spring overrides into tests.
                for key in list(env):
                    if key.startswith(
                        ("PARALLAX_LLM_", "OPENAI_", "SPRING_", "LOGGING_")
                    ):
                        env.pop(key)
                url = f"jdbc:mysql://127.0.0.1:{port}/parallax_test?connectionTimeZone=UTC&forceConnectionTimeZoneToSession=true&allowPublicKeyRetrieval=true&sslMode=DISABLED"
                env["PARALLAX_TEST_DB_URL"] = url
                if source_url:
                    env["PARALLAX_TRANSFER_TEST_SOURCE_URL"] = source_url
                with (output / "maven.log").open("wb") as gate_log:
                    result = subprocess.run(
                        [
                            str(maven),
                            "-o",
                            "-B",
                            "-f",
                            str(root / "gateway/pom.xml"),
                            "verify",
                            "-DskipTests=false",
                            "-Dtest=PlatformIdentityIntegrationTest,WorkerProtocolTest",
                            "-Dit.test=MysqlPersistenceIT",
                            "-DskipITs=false",
                            "-Dparallax.test.mysql=true",
                        ],
                        check=False,
                        cwd=root,
                        env=env,
                        stdout=gate_log,
                        stderr=subprocess.STDOUT,
                        creationflags=flags,
                        timeout=600,
                    )
                print(f"Real MySQL gate exit={result.returncode}; logs={output}")
                return result.returncode
            finally:
                if process.poll() is None:
                    shutdown_env = os.environ.copy()
                    shutdown_env["MYSQL_PWD"] = root_password
                    try:
                        subprocess.run(
                            command,
                            check=False,
                            input="SHUTDOWN;",
                            text=True,
                            env=shutdown_env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=flags,
                            timeout=10,
                        )
                        process.wait(timeout=15)
                    except (subprocess.TimeoutExpired, OSError):
                        process.kill()
                        process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
