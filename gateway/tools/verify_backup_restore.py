"""Backup and restore drill against a real MySQL: dump, restore into a scratch schema, compare checksums.

Never touches the user's database: every run creates two throwaway schemas (source and restore target),
applies the repository migrations in order, seeds rows, then verifies object-by-object equality.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PORT = 3307


def run(command: list[str], *, stdin: str | None = None, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "command failed: " + " ".join(command) + "\n" + (result.stderr or "")[:2000]
        )
    return result.stdout


def sql(client: Path, password: str, statement: str, database: str | None = None) -> str:
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    command = [str(client), "--protocol=TCP", "--host=127.0.0.1", f"--port={PORT}", "--user=root", "--batch", "--raw"]
    if database:
        command.append(database)
    return run(command, stdin=statement, env=env)


def split_statements(text: str) -> list[str]:
    """Split a migration file into statements, ignoring comments and keeping DELIMITER-free DDL."""
    stripped = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    return [part.strip() for part in stripped.split(";") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysql-home", type=Path, required=True)
    parser.add_argument("--password", required=True, help="root password of the local MySQL instance")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    global PORT
    PORT = args.port
    home = args.mysql_home.resolve(strict=True)
    client = home / "bin" / ("mysql.exe" if os.name == "nt" else "mysql")
    dump = home / "bin" / ("mysqldump.exe" if os.name == "nt" else "mysqldump")
    for binary in (client, dump):
        if not binary.is_file():
            parser.error(f"missing binary: {binary}")

    root = Path(__file__).resolve().parents[2]
    migrations = sorted(
        (root / "gateway/src/main/resources/db/mysql").glob("V*.sql"),
        key=lambda path: int(re.match(r"V(\d+)", path.name).group(1)),
    )
    if not migrations:
        parser.error("no mysql migrations found")

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source, target = "parallax_backup_src", "parallax_backup_dst"

    sql(client, args.password, f"DROP DATABASE IF EXISTS {source}; DROP DATABASE IF EXISTS {target};"
                               f"CREATE DATABASE {source} CHARACTER SET utf8mb4;"
                               f"CREATE DATABASE {target} CHARACTER SET utf8mb4;")

    applied = 0
    for migration in migrations:
        for statement in split_statements(migration.read_text(encoding="utf-8")):
            sql(client, args.password, statement + ";", source)
        applied += 1

    seed = """
INSERT INTO platform_user (id, username, password_hash, disabled, created_at) VALUES
  ('seed-user-1', 'backup.alice', 'hash-alice', FALSE, '2026-10-20 10:00:00.123456'),
  ('seed-user-2', 'backup.中文', 'hash-中文', TRUE, '2026-10-20 11:00:00.000001');
INSERT INTO platform_organization (id, name, created_at) VALUES ('seed-org-1', '备份演练组织', '2026-10-20 10:00:00');
INSERT INTO platform_project (id, organization_id, name, created_at) VALUES ('seed-project-1', 'seed-org-1', '备份项目', '2026-10-20 10:00:00');
UPDATE platform_user SET username = CONCAT(username, ' 😀') WHERE id = 'seed-user-2';
"""
    sql(client, args.password, seed, source)

    tables = [
        row.split("\t")[0]
        for row in sql(
            client,
            args.password,
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema = '{source}' AND table_type = 'BASE TABLE' ORDER BY table_name;",
        ).splitlines()[1:]
        if row.strip()
    ]
    if not tables:
        raise RuntimeError("source schema has no tables")

    dump_file = output / "parallax.sql"
    env = os.environ.copy()
    env["MYSQL_PWD"] = args.password
    with dump_file.open("wb") as stream:
        result = subprocess.run(
            [str(dump), "--protocol=TCP", "--host=127.0.0.1", f"--port={PORT}", "--user=root",
             "--single-transaction", "--routines", "--triggers", "--events", "--hex-blob",
             "--set-gtid-purged=OFF", "--databases", source],
            stdout=stream,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=180,
        )
    if result.returncode != 0:
        raise RuntimeError("mysqldump failed: " + result.stderr.decode("utf-8", "replace")[:2000])

    dump_sql = dump_file.read_text(encoding="utf-8")
    dump_sql = dump_sql.replace(f"`{source}`", f"`{target}`").replace(f"USE `{source}`", f"USE `{target}`")
    sql(client, args.password, dump_sql)

    mismatches: list[str] = []
    for table in tables:
        src = sql(client, args.password, f"CHECKSUM TABLE {table};", source).splitlines()[1].split("\t")[1]
        dst = sql(client, args.password, f"CHECKSUM TABLE {table};", target).splitlines()[1].split("\t")[1]
        if src != dst or src == "NULL":
            mismatches.append(f"{table}: source={src} restored={dst}")
        print(f"{table}: checksum={src}")

    counts = {}
    for table in tables:
        src = int(sql(client, args.password, f"SELECT COUNT(*) FROM {table};", source).splitlines()[1])
        dst = int(sql(client, args.password, f"SELECT COUNT(*) FROM {table};", target).splitlines()[1])
        counts[table] = {"source": src, "restored": dst}
        if src != dst:
            mismatches.append(f"{table}: rows source={src} restored={dst}")

    sql(client, args.password, f"DROP DATABASE {source}; DROP DATABASE {target};")

    report = {
        "mysql": "8.4",
        "migrations_applied": applied,
        "tables": len(tables),
        "dump_bytes": dump_file.stat().st_size,
        "checksum_mismatches": mismatches,
        "rows": counts,
        "passed": not mismatches,
    }
    (output / "backup-restore.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"backup/restore passed={report['passed']} tables={len(tables)} dump={report['dump_bytes']} bytes")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
