"""Review store tests (CAT-009): conditional writes, operation-ID
idempotency and schema guards against real SQLite — not mocked state."""

import threading
from pathlib import Path

import pytest

from cateniq.store import (
    ConflictError,
    OperationConflictError,
    ReviewStore,
    SchemaError,
    ValidationError,
)

HASH = "ab" * 32
EDITS = {"S2": {"attach_a": [50, 0, 12], "attach_b": [95, 0, 12]}}


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    s = ReviewStore(tmp_path / "reviews.db")
    s.review("corridor-a", HASH)
    return s


def op(n: int) -> str:
    return f"op-{n:08d}"


class TestConditionalWrites:
    def test_save_advances_revision_and_stores_constraints(
        self, store: ReviewStore
    ) -> None:
        out = store.save("corridor-a", op(1), 0, EDITS)
        assert out == {"operation_id": op(1), "revision": 1, "replayed": False}
        state = store.review("corridor-a", HASH)
        assert state["revision"] == 1
        assert state["constraints"] == EDITS

    def test_stale_base_is_rejected_and_state_untouched(
        self, store: ReviewStore
    ) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        with pytest.raises(ConflictError) as e:
            store.save(
                "corridor-a",
                op(2),
                0,
                {"S1": {"attach_a": [0, 0, 10], "attach_b": [45, 0, 10]}},
            )
        assert e.value.current_revision == 1
        state = store.review("corridor-a", HASH)
        assert state["revision"] == 1
        assert state["constraints"] == EDITS  # no partial update

    def test_concurrent_same_base_saves_allow_exactly_one_winner(
        self, store: ReviewStore
    ) -> None:
        results: list[dict] = []
        errors: list[Exception] = []

        def try_save(n: int) -> None:
            try:
                results.append(store.save("corridor-a", op(n), 0, EDITS))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=try_save, args=(i,)) for i in range(1, 5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 1 and len(errors) == 3
        assert all(isinstance(e, ConflictError) for e in errors)
        assert store.review("corridor-a", HASH)["revision"] == 1

    def test_manifest_hash_mismatch_is_an_explicit_error(
        self, store: ReviewStore
    ) -> None:
        with pytest.raises(Exception, match="manifest changed"):
            store.review("corridor-a", "cd" * 32)


class TestOperationIdempotency:
    def test_identical_retry_replays_without_advancing(
        self, store: ReviewStore
    ) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        store.save(
            "corridor-a",
            op(2),
            1,
            EDITS | {"S3": {"attach_a": [95, 0, 12], "attach_b": [140, 0, 11]}},
        )
        out = store.save("corridor-a", op(1), 0, EDITS)
        assert out["replayed"] is True and out["revision"] == 1
        # Revision did not advance again.
        assert store.review("corridor-a", HASH)["revision"] == 2

    def test_same_id_different_content_is_an_error(self, store: ReviewStore) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        changed = {"S2": {"attach_a": [50, 0, 12], "attach_b": [95, 0, 13]}}
        with pytest.raises(OperationConflictError):
            store.save("corridor-a", op(1), 1, changed)

    def test_operation_id_bounds(self, store: ReviewStore) -> None:
        with pytest.raises(ValidationError):
            store.save("corridor-a", "short", 0, EDITS)


class TestSchemaGuard:
    def test_wrong_schema_version_is_rejected(self, tmp_path: Path) -> None:
        import sqlite3

        path = tmp_path / "v9.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('schema_version', '9')")
        conn.commit()
        conn.close()
        with pytest.raises(SchemaError):
            ReviewStore(path)


class TestRunAttempts:
    def test_operation_id_dedupes_attempts(self, store: ReviewStore) -> None:
        a = store.create_run("corridor-a", op(10), 0)
        b = store.create_run("corridor-a", op(10), 0)
        assert b["replayed"] is True and b["attempt_id"] == a["attempt_id"]

    def test_restart_marks_active_attempts_interrupted(self, tmp_path: Path) -> None:
        path = tmp_path / "reviews.db"
        s1 = ReviewStore(path)
        s1.review("corridor-a", HASH)
        a = s1.create_run("corridor-a", op(10), 0)
        s1.set_run_state(a["attempt_id"], "running", "fit")
        s1.close()
        s2 = ReviewStore(path)  # simulates process restart
        run = s2.run("corridor-a", a["attempt_id"])
        assert run is not None and run["state"] == "interrupted"
        s2.close()

    def test_late_result_cannot_become_current_validation(
        self, store: ReviewStore
    ) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        run = store.create_run("corridor-a", op(10), 1)
        # A later edit lands while the run is in flight.
        store.save("corridor-a", op(2), 1, EDITS)
        store.set_run_state(
            run["attempt_id"],
            "succeeded",
            "output_validation",
            {"spans": [], "issue_count": 0},
        )
        # The run is retained but its input revision (1) is not current (2).
        assert store.run("corridor-a", run["attempt_id"])["state"] == "succeeded"
        assert store.current_validation("corridor-a") is None


class TestAcceptance:
    def test_acceptance_requires_matching_clean_run(self, store: ReviewStore) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        run = store.create_run("corridor-a", op(10), 1)
        clean = {"spans": [{"span_id": "S2", "issues": []}], "issue_count": 0}
        store.set_run_state(run["attempt_id"], "succeeded", "output_validation", clean)
        out = store.accept("corridor-a", 1, run["attempt_id"])
        assert out["revision"] == 1
        assert (
            store.review("corridor-a", HASH)["accepted"]["run_id"] == run["attempt_id"]
        )

    def test_issues_block_acceptance(self, store: ReviewStore) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        run = store.create_run("corridor-a", op(10), 1)
        dirty = {
            "spans": [{"span_id": "S2", "issues": [{"kind": "high_residual"}]}],
            "issue_count": 1,
        }
        store.set_run_state(run["attempt_id"], "succeeded", "output_validation", dirty)
        with pytest.raises(ValidationError):
            store.accept("corridor-a", 1, run["attempt_id"])

    def test_later_edit_invalidates_acceptance_path(self, store: ReviewStore) -> None:
        store.save("corridor-a", op(1), 0, EDITS)
        run = store.create_run("corridor-a", op(10), 1)
        store.set_run_state(
            run["attempt_id"],
            "succeeded",
            "output_validation",
            {"spans": [{"span_id": "S2", "issues": []}], "issue_count": 0},
        )
        store.save("corridor-a", op(2), 1, EDITS)  # revision now 2
        with pytest.raises(ConflictError):
            store.accept("corridor-a", 1, run["attempt_id"])


@pytest.fixture
def client(tmp_path: Path):
    from fastapi.testclient import TestClient

    from cateniq.app import create_app

    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    return TestClient(create_app(fixtures, tmp_path / "reviews.db"))


class TestReviewApi:
    def test_save_reopen_conflict_and_replay(self, client) -> None:
        state = client.get("/api/datasets/corridor-a/review").json()
        assert state["revision"] == 0
        body = {
            "operation_id": "save-0001",
            "base_revision": 0,
            "edits": EDITS,
        }
        out = client.post(
            "/api/datasets/corridor-a/review/operations", json=body
        ).json()
        assert out["revision"] == 1 and not out["replayed"]
        # Identical retry replays — no second revision.
        again = client.post(
            "/api/datasets/corridor-a/review/operations", json=body
        ).json()
        assert again["replayed"] is True and again["revision"] == 1
        # A stale base is rejected with the current revision echoed.
        conflict = client.post(
            "/api/datasets/corridor-a/review/operations",
            json={**body, "operation_id": "save-0002"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["current_revision"] == 1
        # Saved constraints reopen from durable state.
        state = client.get("/api/datasets/corridor-a/review").json()
        assert state["revision"] == 1 and state["constraints"] == EDITS

    def test_export_reconstructs_and_rejects_mismatch(self, client) -> None:
        client.post(
            "/api/datasets/corridor-a/review/operations",
            json={
                "operation_id": "save-0001",
                "base_revision": 0,
                "edits": EDITS,
            },
        )
        export = client.get("/api/datasets/corridor-a/review/export").json()
        ok = client.post("/api/export/verify", json={"export": export}).json()
        assert ok["ok"] is True and ok["constraints"] == EDITS
        # A tampered constraint set fails reconstruction.
        tampered = dict(export, constraints={})
        bad = client.post("/api/export/verify", json={"export": tampered})
        assert bad.status_code == 422
        # An export bound to a different dataset identity is rejected.
        other = client.get("/api/datasets/corridor-b/review/export").json()
        other["constraints"] = EDITS
        other["operations"] = export["operations"]
        other["revision"] = 1
        bad2 = client.post("/api/export/verify", json={"export": other})
        assert bad2.status_code == 422
