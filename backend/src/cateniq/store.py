"""Durable review store (CAT-009).

SQLite persistence for review revisions, append-only correction operations,
bounded run attempts and acceptance — per the frozen implementation profile
in docs/project/features/review-lifecycle.md.

Threading: one connection guarded by a re-entrant lock (FastAPI sync routes
run in a threadpool); writes additionally serialise through BEGIN IMMEDIATE
transactions, so the conditional-save checks are atomic even if the lock is
ever bypassed.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ALGORITHM = "vertex-catenary-1.0"

MAX_EDITED_ENDPOINTS = 128
OP_ID_MIN_LEN, OP_ID_MAX_LEN = 8, 64
RUN_QUEUE_MAX = 8
RUN_DEADLINE_S = 30.0

RUN_STATES = ("queued", "running", "succeeded", "failed", "interrupted")
RUN_STAGES = ("input_validation", "fit", "output_validation")

_DDL = """
CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews(
    dataset_id TEXT PRIMARY KEY,
    manifest_hash TEXT NOT NULL,
    current_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operations(
    review TEXT NOT NULL,
    seq INTEGER NOT NULL,
    operation_id TEXT NOT NULL,
    base_revision INTEGER NOT NULL,
    result_revision INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (review, seq),
    UNIQUE (review, operation_id)
);
CREATE TABLE IF NOT EXISTS runs(
    attempt_id INTEGER PRIMARY KEY,
    review TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    input_revision INTEGER NOT NULL,
    algorithm TEXT NOT NULL,
    state TEXT NOT NULL,
    stage TEXT NOT NULL,
    result TEXT,
    retry_of INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE (review, operation_id)
);
CREATE TABLE IF NOT EXISTS acceptance(
    review TEXT NOT NULL,
    revision INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    accepted_at TEXT NOT NULL,
    PRIMARY KEY (review, revision)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class StoreError(RuntimeError):
    """Explicit store failure — never a silent reset or false success."""


class SchemaError(StoreError):
    """Store schema version is not the supported one."""


class ConflictError(StoreError):
    """Conditional-write failure: base revision is no longer current."""

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"base revision is not current: {current_revision}")
        self.current_revision = current_revision


class OperationConflictError(StoreError):
    """Operation ID reused with different content."""


class ValidationError(StoreError):
    """Request payload violates the contract."""


class ReviewStore:
    """One SQLite file holding every review's durable state."""

    def __init__(self, path: str | Path) -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()
        # Restart recovery: attempts left queued/running by a previous
        # process are marked interrupted — recovery from durable inputs,
        # not checkpoint resume.
        self._conn.execute(
            "UPDATE runs SET state='interrupted', finished_at=? "
            "WHERE state IN ('queued','running')",
            (_now(),),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_DDL)
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO meta(key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row[0]) != SCHEMA_VERSION:
                raise SchemaError(
                    f"store schema_version {row[0]} != {SCHEMA_VERSION}; "
                    "no automatic migration exists"
                )

    # -- reviews -------------------------------------------------------------

    def review(self, dataset_id: str, manifest_hash: str) -> dict[str, Any]:
        """Fetch or create the review bound to one dataset identity."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM reviews WHERE dataset_id=?", (dataset_id,)
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO reviews(dataset_id, manifest_hash,"
                    " current_revision, created_at) VALUES (?,?,0,?)",
                    (dataset_id, manifest_hash, _now()),
                )
                revision = 0
            else:
                if row["manifest_hash"] != manifest_hash:
                    raise StoreError(
                        f"dataset {dataset_id} manifest changed: stored "
                        f"{row['manifest_hash'][:12]} != {manifest_hash[:12]}"
                    )
                revision = row["current_revision"]
        acc = self._conn.execute(
            "SELECT * FROM acceptance WHERE review=? AND revision=?",
            (dataset_id, revision),
        ).fetchone()
        return {
            "dataset_id": dataset_id,
            "manifest_hash": manifest_hash,
            "revision": revision,
            "accepted": (
                {
                    "revision": acc["revision"],
                    "run_id": acc["run_id"],
                    "at": acc["accepted_at"],
                }
                if acc
                else None
            ),
            "constraints": self.constraints(dataset_id),
        }

    def constraints(self, dataset_id: str) -> dict[str, Any]:
        """Effective saved constraint set at the current revision."""
        row = self._conn.execute(
            "SELECT payload FROM operations WHERE review=? ORDER BY seq DESC LIMIT 1",
            (dataset_id,),
        ).fetchone()
        return json.loads(row["payload"])["edits"] if row else {}

    def constraints_at(self, dataset_id: str, revision: int) -> dict[str, Any]:
        """Effective constraint set as of a specific revision — a run's
        declared inputs, immune to later edits."""
        if revision == 0:
            return {}
        row = self._conn.execute(
            "SELECT payload FROM operations WHERE review=? AND result_revision=?",
            (dataset_id, revision),
        ).fetchone()
        if row is None:
            raise StoreError(f"no operation produced revision {revision}")
        edits: dict[str, Any] = json.loads(row["payload"])["edits"]
        return edits

    def run_by_id(self, attempt_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        return self._run_row(row) if row else None

    # -- conditional saves ---------------------------------------------------

    def save(
        self,
        dataset_id: str,
        operation_id: str,
        base_revision: int,
        edits: dict[str, Any],
    ) -> dict[str, Any]:
        """Append one operation iff base_revision is current.

        Identical retry of a completed operation replays its outcome without
        advancing the revision; the same ID with different content is an
        error. Two same-base writers serialise through BEGIN IMMEDIATE —
        at most one advances.
        """
        if not (OP_ID_MIN_LEN <= len(operation_id) <= OP_ID_MAX_LEN):
            raise ValidationError(
                f"operation_id length {len(operation_id)} outside"
                f" [{OP_ID_MIN_LEN}, {OP_ID_MAX_LEN}]"
            )
        payload = {"edits": edits}
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    "SELECT payload, result_revision FROM operations"
                    " WHERE review=? AND operation_id=?",
                    (dataset_id, operation_id),
                ).fetchone()
                if existing is not None:
                    if json.loads(existing["payload"]) == payload:
                        self._conn.execute("COMMIT")
                        return {
                            "operation_id": operation_id,
                            "revision": existing["result_revision"],
                            "replayed": True,
                        }
                    raise OperationConflictError(
                        f"operation_id {operation_id} already used with"
                        " different content"
                    )
                rev = self._conn.execute(
                    "SELECT current_revision FROM reviews WHERE dataset_id=?",
                    (dataset_id,),
                ).fetchone()
                if rev is None:
                    raise StoreError(f"no review for {dataset_id}")
                if rev["current_revision"] != base_revision:
                    raise ConflictError(rev["current_revision"])
                new_rev = base_revision + 1
                seq = self._conn.execute(
                    "SELECT COALESCE(MAX(seq),0)+1 FROM operations WHERE review=?",
                    (dataset_id,),
                ).fetchone()[0]
                self._conn.execute(
                    "INSERT INTO operations(review, seq, operation_id,"
                    " base_revision, result_revision, payload, created_at)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (
                        dataset_id,
                        seq,
                        operation_id,
                        base_revision,
                        new_rev,
                        json.dumps(payload, sort_keys=True),
                        _now(),
                    ),
                )
                self._conn.execute(
                    "UPDATE reviews SET current_revision=? WHERE dataset_id=?",
                    (new_rev, dataset_id),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return {
            "operation_id": operation_id,
            "revision": new_rev,
            "replayed": False,
        }

    # -- run attempts --------------------------------------------------------

    def active_runs(self, dataset_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM runs WHERE review=?"
            " AND state IN ('queued','running')",
            (dataset_id,),
        ).fetchone()
        return int(row[0])

    def create_run(
        self,
        dataset_id: str,
        operation_id: str,
        input_revision: int,
        retry_of: int | None = None,
    ) -> dict[str, Any]:
        """Admit one attempt; an existing operation ID replays its attempt."""
        if not (OP_ID_MIN_LEN <= len(operation_id) <= OP_ID_MAX_LEN):
            raise ValidationError("invalid operation_id")
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT attempt_id, state FROM runs WHERE review=? AND operation_id=?",
                (dataset_id, operation_id),
            ).fetchone()
            if existing is not None:
                return {
                    "attempt_id": existing["attempt_id"],
                    "state": existing["state"],
                    "replayed": True,
                }
            if self.active_runs(dataset_id) >= RUN_QUEUE_MAX:
                raise StoreError("run queue is full; retry later")
            cur = self._conn.execute(
                "INSERT INTO runs(review, operation_id, input_revision,"
                " algorithm, state, stage, retry_of, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    dataset_id,
                    operation_id,
                    input_revision,
                    ALGORITHM,
                    "queued",
                    "input_validation",
                    retry_of,
                    _now(),
                ),
            )
            return {
                "attempt_id": cur.lastrowid,
                "state": "queued",
                "replayed": False,
            }

    def set_run_state(
        self,
        attempt_id: int,
        state: str,
        stage: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        if state not in RUN_STATES or stage not in RUN_STAGES:
            raise ValidationError(f"invalid run state {state}/{stage}")
        cols = ["state=?", "stage=?"]
        vals: list[Any] = [state, stage]
        if result is not None:
            cols.append("result=?")
            vals.append(json.dumps(result, sort_keys=True))
        if state == "running":
            cols.append("started_at=?")
            vals.append(_now())
        if state in ("succeeded", "failed", "interrupted"):
            cols.append("finished_at=?")
            vals.append(_now())
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE runs SET {', '.join(cols)} WHERE attempt_id=?",
                (*vals, attempt_id),
            )

    @staticmethod
    def _run_row(row: sqlite3.Row) -> dict[str, Any]:
        out = dict(row)
        out["result"] = json.loads(row["result"]) if row["result"] else None
        return out

    def run(self, dataset_id: str, attempt_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE review=? AND attempt_id=?",
            (dataset_id, attempt_id),
        ).fetchone()
        return self._run_row(row) if row else None

    def current_validation(self, dataset_id: str) -> dict[str, Any] | None:
        """Latest succeeded run whose inputs are the current revision."""
        rev = self._conn.execute(
            "SELECT current_revision FROM reviews WHERE dataset_id=?",
            (dataset_id,),
        ).fetchone()
        if rev is None:
            return None
        row = self._conn.execute(
            "SELECT * FROM runs WHERE review=? AND input_revision=?"
            " AND state='succeeded' ORDER BY finished_at DESC LIMIT 1",
            (dataset_id, rev["current_revision"]),
        ).fetchone()
        return self._run_row(row) if row else None

    # -- acceptance ----------------------------------------------------------

    def accept(self, dataset_id: str, revision: int, run_id: int) -> dict[str, Any]:
        """Accept an exact revision iff its validation succeeded cleanly."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rev = self._conn.execute(
                    "SELECT current_revision FROM reviews WHERE dataset_id=?",
                    (dataset_id,),
                ).fetchone()
                if rev is None or rev["current_revision"] != revision:
                    raise ConflictError(rev["current_revision"] if rev else -1)
                run = self._conn.execute(
                    "SELECT state, input_revision, result FROM runs"
                    " WHERE attempt_id=? AND review=?",
                    (run_id, dataset_id),
                ).fetchone()
                if (
                    run is None
                    or run["state"] != "succeeded"
                    or run["input_revision"] != revision
                ):
                    raise ConflictError(revision)
                result = json.loads(run["result"])
                blocking = sum(len(s.get("issues", [])) for s in result["spans"])
                if blocking:
                    raise ValidationError(
                        f"validation has {blocking} unresolved issue(s);"
                        " acceptance requires a clean run"
                    )
                self._conn.execute(
                    "INSERT OR REPLACE INTO acceptance"
                    "(review, revision, run_id, accepted_at) VALUES (?,?,?,?)",
                    (dataset_id, revision, run_id, _now()),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return {"revision": revision, "run_id": run_id, "at": _now()}

    # -- export --------------------------------------------------------------

    def history(self, dataset_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT seq, operation_id, base_revision, result_revision,"
            " payload, created_at FROM operations WHERE review=? ORDER BY seq",
            (dataset_id,),
        ).fetchall()
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]

    def runs_for_export(self, dataset_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM runs WHERE review=? ORDER BY attempt_id",
            (dataset_id,),
        ).fetchall()
        return [dict(r) for r in rows]
