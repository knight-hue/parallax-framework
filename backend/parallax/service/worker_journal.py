"""Local delivery journal, never an alternative authority for platform task state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from parallax.service.worker_protocol import WorkerEvent, WorkerTask


class JournalConflict(ValueError):
    """A delivery contradicts an already persisted contract or event."""


class WorkerJournal:
    """Fsync before acknowledging HTTP; one launch per attempt on this worker volume.

    CLAIMED work is deliberately never re-launched on restart: Java must expire its
    lease. SQLite is a local execution/delivery spool, not shared cross-node state.
    Cross-node execution is fenced by Java STARTED and its current attempt.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS execution (
                    task_id TEXT NOT NULL, attempt INTEGER NOT NULL, fence INTEGER NOT NULL,
                    contract TEXT NOT NULL, launch_state TEXT NOT NULL DEFAULT 'NEW',
                    sequence INTEGER NOT NULL DEFAULT 0,
                    prompt INTEGER NOT NULL DEFAULT 0, completion INTEGER NOT NULL DEFAULT 0,
                    canceled INTEGER NOT NULL DEFAULT 0, terminal INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(task_id, attempt)
                );
                CREATE TABLE IF NOT EXISTS delivery (
                    event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                    sequence INTEGER NOT NULL, payload TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(task_id, attempt, sequence),
                    FOREIGN KEY(task_id, attempt) REFERENCES execution(task_id, attempt)
                );
            """)

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @contextmanager
    def _write(self):
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _contract(task: WorkerTask) -> str:
        # Trace is diagnostic; execution inputs are otherwise immutable.
        return json.dumps(
            task.model_dump(mode="json", exclude={"trace_id"}),
            sort_keys=True,
            separators=(",", ":"),
        )

    def register(self, task: WorkerTask) -> bool:
        contract = self._contract(task)
        with self._write() as conn:
            row = conn.execute(
                "SELECT contract FROM execution WHERE task_id=? AND attempt=?",
                (task.task_id, task.attempt),
            ).fetchone()
            if row:
                if row[0] != contract:
                    raise JournalConflict("Dispatch changed an existing execution contract")
                return False
            conn.execute(
                "INSERT INTO execution(task_id,attempt,fence,contract) VALUES (?,?,?,?)",
                (task.task_id, task.attempt, task.fencing_token, contract),
            )
            return True

    def claim_launch(self, task: WorkerTask) -> bool:
        with self._write() as conn:
            self._current(conn, task)
            return (
                conn.execute(
                    "UPDATE execution SET launch_state='CLAIMED' WHERE task_id=? AND attempt=? AND launch_state='NEW'",
                    (task.task_id, task.attempt),
                ).rowcount
                == 1
            )

    def request_cancel(self, task: WorkerTask) -> None:
        # Persists even if cancel arrived before dispatch. It cannot authorize a
        # CANCELED event: the worker still checks the platform's acknowledgement.
        self.register(task)
        with self._write() as conn:
            self._current(conn, task)
            conn.execute(
                "UPDATE execution SET canceled=1 WHERE task_id=? AND attempt=?",
                (task.task_id, task.attempt),
            )

    def canceled(self, task: WorkerTask) -> bool:
        with closing(self._connect()) as conn:
            return bool(self._current(conn, task)["canceled"])

    def prepare(
        self,
        task: WorkerTask,
        kind: str,
        prompt: int,
        completion: int,
        result_sha256: str | None = None,
    ) -> WorkerEvent:
        with self._write() as conn:
            row = self._current(conn, task)
            pending = conn.execute(
                "SELECT payload FROM delivery WHERE task_id=? AND attempt=? AND acknowledged=0",
                (task.task_id, task.attempt),
            ).fetchone()
            if pending:
                event = WorkerEvent.model_validate_json(pending[0])
                if (
                    event.kind,
                    event.prompt_tokens,
                    event.completion_tokens,
                    event.result_sha256,
                ) != (kind, prompt, completion, result_sha256):
                    raise JournalConflict(
                        "An earlier event must be acknowledged before preparing another"
                    )
                return event
            if row["terminal"] or row["launch_state"] != "CLAIMED":
                raise JournalConflict("Execution is not active")
            if (
                prompt < row["prompt"]
                or completion < row["completion"]
                or prompt + completion > task.token_budget
            ):
                raise JournalConflict("Usage must be monotonic and within the reservation")
            sequence = row["sequence"] + 1
            if (
                sequence == 1
                and (kind not in {"STARTED", "FAILED", "CANCELED"} or prompt + completion != 0)
            ) or (sequence > 1 and kind == "STARTED"):
                raise JournalConflict("Execution must begin with a zero-usage grant event")
            event = WorkerEvent(
                schema_version=1,
                event_id=uuid4().hex,
                task_id=task.task_id,
                attempt=task.attempt,
                fencing_token=task.fencing_token,
                sequence=sequence,
                kind=kind,
                occurred_at=datetime.now(UTC),
                prompt_tokens=prompt,
                completion_tokens=completion,
                result_sha256=result_sha256,
            )
            conn.execute(
                "INSERT INTO delivery(event_id,task_id,attempt,sequence,payload) VALUES (?,?,?,?,?)",
                (event.event_id, task.task_id, task.attempt, sequence, event.model_dump_json()),
            )
            conn.execute(
                "UPDATE execution SET sequence=?,prompt=?,completion=?,terminal=? WHERE task_id=? AND attempt=?",
                (
                    sequence,
                    prompt,
                    completion,
                    kind in {"FAILED", "CANCELED", "SUCCEEDED"},
                    task.task_id,
                    task.attempt,
                ),
            )
            return event

    def acknowledge(self, event: WorkerEvent) -> None:
        with self._write() as conn:
            row = conn.execute(
                "SELECT payload FROM delivery WHERE event_id=?", (event.event_id,)
            ).fetchone()
            if row is None or WorkerEvent.model_validate_json(row[0]) != event:
                raise JournalConflict("Acknowledgement differs from the persisted event")
            conn.execute("UPDATE delivery SET acknowledged=1 WHERE event_id=?", (event.event_id,))

    def is_pending(self, event: WorkerEvent) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT acknowledged FROM delivery WHERE event_id=?", (event.event_id,)
            ).fetchone()
            return row is not None and row[0] == 0

    def pending(self, limit: int = 100) -> list[WorkerEvent]:
        if not 1 <= limit <= 100:
            raise ValueError("Delivery batch must be 1..100")
        with closing(self._connect()) as conn:
            return [
                WorkerEvent.model_validate_json(row[0])
                for row in conn.execute(
                    "SELECT payload FROM delivery WHERE acknowledged=0 ORDER BY rowid LIMIT ?",
                    (limit,),
                )
            ]

    def unclaimed(self, limit: int = 100) -> list[WorkerTask]:
        if not 1 <= limit <= 100:
            raise ValueError("Dispatch batch must be 1..100")
        with closing(self._connect()) as conn:
            return [
                WorkerTask.model_validate_json(row[0])
                for row in conn.execute(
                    "SELECT contract FROM execution WHERE launch_state='NEW' ORDER BY rowid LIMIT ?",
                    (limit,),
                )
            ]

    def _current(self, conn, task: WorkerTask):
        row = conn.execute(
            "SELECT * FROM execution WHERE task_id=? AND attempt=?", (task.task_id, task.attempt)
        ).fetchone()
        if row is None or row["contract"] != self._contract(task):
            raise JournalConflict("Unknown or changed execution contract")
        return row
