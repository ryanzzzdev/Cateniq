"""Review store tests (CAT-009): conditional writes, operation-ID
idempotency and schema guards against real SQLite — not mocked state."""

import os
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from cateniq.store import (
    ConflictError,
    OperationConflictError,
    ReviewStore,
    SchemaError,
    StoreError,
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


class TestFaults:
    """CAT-011 fault cases: failures surface as errors and prior durable
    state survives — never a silent reset."""

    def test_corrupt_db_fails_explicitly(self, tmp_path: Path) -> None:
        path = tmp_path / "garbage.db"
        path.write_bytes(b"not a sqlite database" * 4)
        with pytest.raises(sqlite3.DatabaseError):
            ReviewStore(path)

    def test_write_failure_surfaces_and_prior_state_survives(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "reviews.db"
        s = ReviewStore(path)
        s.review("corridor-a", HASH)
        s.save("corridor-a", op(1), 0, EDITS)
        # A broken write path fails explicitly — never a silent success —
        # and committed state survives intact.
        s._conn.close()
        with pytest.raises(sqlite3.ProgrammingError):
            s.save("corridor-a", op(2), 1, EDITS)
        again = ReviewStore(path)
        assert again.review("corridor-a", HASH)["revision"] == 1
        again.close()


class TestRunAttempts:
    def test_operation_id_dedupes_attempts(self, store: ReviewStore) -> None:
        a = store.create_run("corridor-a", op(10), 0)
        b = store.create_run("corridor-a", op(10), 0)
        assert b["replayed"] is True and b["attempt_id"] == a["attempt_id"]

    def test_queue_bound_rejects_ninth_active_run(self, store: ReviewStore) -> None:
        # Contract: queue depth 8 — the ninth admitted run is refused.
        for i in range(8):
            store.create_run("corridor-a", op(20 + i), 0)
        with pytest.raises(StoreError):
            store.create_run("corridor-a", op(99), 0)

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


class TestRunApi:
    """Run lifecycle through the API with the executor driven manually —
    deterministic, no timing dependencies."""

    @pytest.fixture
    def client(self, tmp_path: Path):
        from fastapi.testclient import TestClient

        from cateniq.app import create_app

        fixtures = Path(__file__).resolve().parents[2] / "fixtures"
        return TestClient(
            create_app(fixtures, tmp_path / "reviews.db", run_executor=False)
        )

    def _save(self, client) -> None:
        client.post(
            "/api/datasets/corridor-a/review/operations",
            json={"operation_id": "save-0001", "base_revision": 0, "edits": EDITS},
        )

    def _drain(self, client) -> None:
        svc = client.app.state.service
        while svc.execute_next():
            pass

    def test_run_executes_against_declared_revision(self, client) -> None:
        self._save(client)
        out = client.post(
            "/api/datasets/corridor-a/review/runs",
            json={"operation_id": "run-00001"},
        ).json()
        assert out["state"] == "queued"
        # Dedupe: the same run operation ID does not create a second attempt.
        again = client.post(
            "/api/datasets/corridor-a/review/runs",
            json={"operation_id": "run-00001"},
        ).json()
        assert again["replayed"] is True
        self._drain(client)
        run = client.get(
            f"/api/datasets/corridor-a/review/runs/{out['attempt_id']}"
        ).json()
        assert run["state"] == "succeeded"
        assert run["input_revision"] == 1
        assert run["result"]["issue_count"] >= 1  # S4 stays unresolved

    def test_late_run_output_cannot_validate_the_wrong_revision(self, client) -> None:
        self._save(client)
        client.post(
            "/api/datasets/corridor-a/review/runs",
            json={"operation_id": "run-00001"},
        )
        # A newer save lands before the queued attempt executes.
        client.post(
            "/api/datasets/corridor-a/review/operations",
            json={
                "operation_id": "save-0002",
                "base_revision": 1,
                "edits": {"S2": {"attach_a": [50, 0, 12], "attach_b": [95, 0, 12.5]}},
            },
        )
        self._drain(client)
        cur = client.get("/api/datasets/corridor-a/review/runs/current").json()
        assert cur["run"] is None  # succeeded, but for revision 1 — not current

    def test_interrupted_run_retries_as_linked_attempt(self, client) -> None:
        # Simulate an interrupted attempt, then retry.
        self._save(client)
        svc = client.app.state.service
        attempt = svc.store.create_run("corridor-a", "run-00001", 1)
        svc.store.set_run_state(attempt["attempt_id"], "interrupted", "fit")
        out = client.post(
            f"/api/datasets/corridor-a/review/runs/{attempt['attempt_id']}/retry",
            json={"operation_id": "run-00002"},
        ).json()
        assert out["state"] == "queued"
        self._drain(client)
        run = client.get(
            f"/api/datasets/corridor-a/review/runs/{out['attempt_id']}"
        ).json()
        assert run["state"] == "succeeded" and run["retry_of"] == attempt["attempt_id"]

    def test_deadline_failure_never_reports_success(self, client) -> None:
        self._save(client)
        client.app.state.service._run_deadline_s = 0.0
        out = client.post(
            "/api/datasets/corridor-a/review/runs",
            json={"operation_id": "run-00001"},
        ).json()
        self._drain(client)
        run = client.get(
            f"/api/datasets/corridor-a/review/runs/{out['attempt_id']}"
        ).json()
        assert run["state"] == "failed"

    def test_queue_overflow_is_rejected_503(self, client) -> None:
        for i in range(8):
            out = client.post(
                "/api/datasets/corridor-a/review/runs",
                json={"operation_id": f"run-{i:05d}"},
            )
            assert out.status_code == 200, out.text
        ninth = client.post(
            "/api/datasets/corridor-a/review/runs",
            json={"operation_id": "run-99999"},
        )
        assert ninth.status_code == 503

    def test_solver_failure_marks_run_failed_with_stage(self, client) -> None:
        self._save(client)
        out = client.post(
            "/api/datasets/corridor-a/review/runs",
            json={"operation_id": "run-00001"},
        ).json()
        svc = client.app.state.service
        original = svc._refit_result

        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("solver exploded")

        svc._refit_result = boom
        try:
            svc.execute_next()
        finally:
            svc._refit_result = original
        run = client.get(
            f"/api/datasets/corridor-a/review/runs/{out['attempt_id']}"
        ).json()
        assert run["state"] == "failed"
        assert run["stage"] == "fit"
        assert "solver exploded" in run["result"]["error"]
        # A failed attempt never becomes current validation.
        assert (
            client.get("/api/datasets/corridor-a/review/runs/current").json()["run"]
            is None
        )

    def test_acceptance_round_trip_and_race(self, client) -> None:
        # corridor-b is clean — a succeeded run has no blocking issues.
        out = client.post(
            "/api/datasets/corridor-b/review/runs",
            json={"operation_id": "run-00001"},
        ).json()
        self._drain(client)
        run = client.get(
            f"/api/datasets/corridor-b/review/runs/{out['attempt_id']}"
        ).json()
        assert run["state"] == "succeeded"
        assert run["result"]["issue_count"] == 0
        acc = client.post(
            "/api/datasets/corridor-b/review/accept",
            json={"revision": 0, "run_id": out["attempt_id"]},
        )
        assert acc.status_code == 200
        state = client.get("/api/datasets/corridor-b/review").json()
        assert state["accepted"]["revision"] == 0
        # A later edit leaves the new revision unaccepted.
        client.post(
            "/api/datasets/corridor-b/review/operations",
            json={
                "operation_id": "save-0001",
                "base_revision": 0,
                "edits": {"B1": {"attach_a": [0, 0, 12], "attach_b": [50, 0, 12]}},
            },
        )
        state = client.get("/api/datasets/corridor-b/review").json()
        assert state["revision"] == 1 and state["accepted"] is None
        # And accepting the stale revision/run is a conflict.
        stale = client.post(
            "/api/datasets/corridor-b/review/accept",
            json={"revision": 0, "run_id": out["attempt_id"]},
        )
        assert stale.status_code == 409


class TestCoherentSnapshots:
    """Exports under a concurrent saver are always self-consistent — a
    save can interleave between exports but never *inside* one."""

    def test_export_is_coherent_under_concurrent_saves(self, tmp_path: Path) -> None:
        fixtures = Path(__file__).resolve().parents[2] / "fixtures"
        from cateniq.service import CorridorService

        svc = CorridorService(fixtures, tmp_path / "reviews.db", run_executor=False)
        stop = threading.Event()

        def saver() -> None:
            for i in range(40):
                rev = svc.review_state("corridor-a")["revision"]
                try:
                    svc.save_operation("corridor-a", f"save-{i:06d}", rev, EDITS)
                except Exception:
                    return
                if stop.is_set():
                    return

        t = threading.Thread(target=saver)
        t.start()
        for _ in range(40):
            export = svc.export_review("corridor-a")
            # The export must verify against its own declared revision —
            # a split read would produce a chain that does not reach it.
            assert svc.verify_export(export)["ok"] is True
        stop.set()
        t.join(timeout=5)
        svc.shutdown()


class TestRealProcessRecovery:
    """CAT-011: an actual OS-level kill — not a simulated restart. A child
    process marks a run running, is SIGKILLed mid-work, and a fresh
    process must recover the durable state."""

    def test_process_kill_marks_run_interrupted_and_retry_recovers(
        self, tmp_path: Path
    ) -> None:
        fixtures = Path(__file__).resolve().parents[2] / "fixtures"
        src = Path(__file__).resolve().parents[1] / "src"
        db = tmp_path / "reviews.db"
        child = tmp_path / "child_run.py"
        child.write_text(
            textwrap.dedent(
                f"""
                import os, sys, time
                sys.path.insert(0, {str(src)!r})
                from pathlib import Path
                from cateniq.service import CorridorService

                svc = CorridorService(
                    Path({str(fixtures)!r}), Path({str(db)!r}),
                    run_executor=False,
                )
                svc.save_operation(
                    "corridor-a", "save-00000001", 0,
                    {{"S2": {{"attach_a": [50, 0, 12], "attach_b": [95, 0, 12]}}}},
                )
                att = svc.start_run("corridor-a", "run-00000001")
                svc.store.set_run_state(att["attempt_id"], "running", "fit")
                print(att["attempt_id"], flush=True)
                time.sleep(60)  # dies here mid-run — never finishes
                """
            )
        )
        proc = subprocess.Popen(
            [sys.executable, str(child)],
            stdout=subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": str(src)},
        )
        assert proc.stdout is not None
        attempt_id = int(proc.stdout.readline().decode().strip())
        proc.kill()  # real SIGKILL mid-run
        proc.wait(timeout=5)
        assert proc.returncode != 0

        # A fresh process over the same database: restart recovery must
        # mark the orphaned run interrupted, and retry must recompute
        # from durable inputs.
        from cateniq.service import CorridorService

        svc = CorridorService(fixtures, db, run_executor=False)
        try:
            run = svc.store.run_by_id(attempt_id)
            assert run is not None and run["state"] == "interrupted"
            retry = svc.start_run("corridor-a", "run-00000002", retry_of=attempt_id)
            svc.execute_next()
            done = svc.store.run_by_id(retry["attempt_id"])
            assert done is not None and done["state"] == "succeeded"
            assert done["retry_of"] == attempt_id
            assert done["input_revision"] == 1
        finally:
            svc.shutdown()


class TestExecutorResponsiveness:
    """CAT-011: the single executor slot is bounded *and* non-blocking —
    the API stays responsive while a slow run occupies the slot."""

    def test_api_stays_responsive_during_a_slow_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fixtures = Path(__file__).resolve().parents[2] / "fixtures"
        from cateniq.service import CorridorService

        svc = CorridorService(fixtures, tmp_path / "reviews.db", run_executor=True)
        try:
            # A slow fit: 100 ms per span keeps the run in-flight for a
            # measurable window.
            original = svc._fit_for

            def slow(*args: object, **kwargs: object) -> dict:
                time.sleep(0.1)
                return original(*args, **kwargs)

            monkeypatch.setattr(svc, "_fit_for", slow)
            svc.save_operation(
                "corridor-a",
                "save-00000001",
                0,
                {"S2": {"attach_a": [50, 0, 12], "attach_b": [95, 0, 12]}},
            )
            out = svc.start_run("corridor-a", "run-00000001")
            for _ in range(100):
                run = svc.store.run_by_id(out["attempt_id"])
                if run and run["state"] == "running":
                    break
                time.sleep(0.01)
            assert run is not None and run["state"] == "running"
            # While the worker is mid-run, a store read completes fast —
            # the executor slot does not block the serving path.
            t0 = time.monotonic()
            state = svc.review_state("corridor-a")
            elapsed = time.monotonic() - t0
            assert elapsed < 0.5, f"review read blocked {elapsed:.2f}s"
            assert state["revision"] == 1
            # The run still completes through the executor.
            for _ in range(200):
                done = svc.store.run_by_id(out["attempt_id"])
                if done and done["state"] in (
                    "succeeded",
                    "failed",
                ):
                    break
                time.sleep(0.05)
            assert done is not None and done["state"] == "succeeded"
        finally:
            svc.shutdown()
