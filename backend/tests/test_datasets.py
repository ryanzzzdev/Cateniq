"""Dataset contract tests (CAT-005): validation, separation, reproducibility,
and the fitting outcomes each fixture case exists to produce."""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from generate_corridor import SPECS

from cateniq import datasets
from cateniq.datasets.gen import generate_dataset
from cateniq.datasets.manifest import ManifestError, load_manifest
from cateniq.datasets.plane import predicted_plane, to_plane
from cateniq.geometry import profile
from cateniq.geometry.catenary import (
    endpoint_deviations,
    fit_constrained,
    fit_free,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _span_uv(manifest, span_id: str, arr):
    predictions = datasets.load_predictions(manifest)
    att, origin, plane_u = predicted_plane(manifest, predictions, span_id)
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
    return att, to_plane(xyz, origin, plane_u)


class TestManifestValidation:
    def test_all_datasets_validate(self) -> None:
        for spec in SPECS:
            m = load_manifest(FIXTURES / spec.dataset_id)
            datasets.verify_assets(m)
            assert {r.span_id for r in m.observations} == {s.span_id for s in m.spans}

    def _corrupt_copy(self, tmp_path: Path, mutate) -> Path:
        dst = tmp_path / "corridor-a"
        shutil.copytree(FIXTURES / "corridor-a", dst)
        mutate(dst)
        return dst

    def test_rejects_unsupported_schema(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            doc = json.loads((d / "manifest.json").read_text())
            doc["schema_version"] = 99
            (d / "manifest.json").write_text(json.dumps(doc))

        with pytest.raises(ManifestError, match="schema_version"):
            load_manifest(self._corrupt_copy(tmp_path, m))

    def test_rejects_wrong_units(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            doc = json.loads((d / "manifest.json").read_text())
            doc["coordinate_convention"]["units"] = "ft"
            (d / "manifest.json").write_text(json.dumps(doc))

        with pytest.raises(ManifestError, match="units"):
            load_manifest(self._corrupt_copy(tmp_path, m))

    def test_rejects_unknown_pole_reference(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            doc = json.loads((d / "manifest.json").read_text())
            doc["topology"]["spans"][0]["pole_b"] = "P9"
            (d / "manifest.json").write_text(json.dumps(doc))

        with pytest.raises(ManifestError, match="pole reference"):
            load_manifest(self._corrupt_copy(tmp_path, m))

    def test_rejects_hash_mismatch(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            f = d / "observations" / "S1.npy"
            arr = np.load(f)
            arr["z"] += 1.0
            np.save(f, arr)

        dst = self._corrupt_copy(tmp_path, m)
        m2 = load_manifest(dst)
        with pytest.raises(ManifestError, match="hash mismatch"):
            datasets.verify_assets(m2)

    def test_rejects_duplicate_point_ids(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            f = d / "observations" / "S1.npy"
            arr = np.load(f)
            arr["point_id"][1] = arr["point_id"][0]
            np.save(f, arr)
            doc = json.loads((d / "manifest.json").read_text())
            for ref in doc["assets"]["observations"]:
                if ref["span_id"] == "S1":
                    ref["sha256"] = _sha256(f)
            (d / "manifest.json").write_text(json.dumps(doc))

        with pytest.raises(ManifestError, match="duplicate point"):
            datasets.load_observations(load_manifest(self._corrupt_copy(tmp_path, m)))

    def test_rejects_nonfinite_coordinates(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            f = d / "observations" / "S1.npy"
            arr = np.load(f)
            arr["z"][0] = np.inf
            np.save(f, arr)
            doc = json.loads((d / "manifest.json").read_text())
            for ref in doc["assets"]["observations"]:
                if ref["span_id"] == "S1":
                    ref["sha256"] = _sha256(f)
            (d / "manifest.json").write_text(json.dumps(doc))

        with pytest.raises(ManifestError, match="non-finite"):
            datasets.load_observations(load_manifest(self._corrupt_copy(tmp_path, m)))

    def test_rejects_point_count_mismatch(self, tmp_path: Path) -> None:
        def m(d: Path) -> None:
            doc = json.loads((d / "manifest.json").read_text())
            for ref in doc["assets"]["observations"]:
                if ref["span_id"] == "S1":
                    ref["point_count"] += 1
            (d / "manifest.json").write_text(json.dumps(doc))

        with pytest.raises(ManifestError, match="count mismatch"):
            datasets.load_observations(load_manifest(self._corrupt_copy(tmp_path, m)))


class TestSeparation:
    def test_fitter_path_never_reads_evaluation(self, tmp_path: Path) -> None:
        # Corrupt the reference file: observation loading must be unaffected.
        dst = tmp_path / "corridor-a"
        shutil.copytree(FIXTURES / "corridor-a", dst)
        (dst / "evaluation" / "reference.json").write_text("corrupted")
        m = load_manifest(dst)
        obs = datasets.load_observations(m)
        assert set(obs) == {"S1", "S2", "S3", "S4"}
        with pytest.raises(ManifestError, match="hash mismatch"):
            datasets.verify_assets(m)

    def test_planted_error_is_declared(self) -> None:
        m = load_manifest(FIXTURES / "corridor-a")
        errors = m.planted_errors
        assert len(errors) == 1 and errors[0]["span_id"] == "S2"
        assert errors[0]["kind"] == "endpoint-displacement"


class TestReproducibility:
    def test_regeneration_is_byte_identical(self, tmp_path: Path) -> None:
        for spec in SPECS:
            a = generate_dataset(tmp_path / "r1", spec)
            b = generate_dataset(tmp_path / "r2", spec)
            files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
            files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
            assert files_a == files_b
            for rel in files_a:
                assert _sha256(a / rel) == _sha256(b / rel), rel


class TestFixtureOutcomes:
    """Each fixture produces its intended fitter/diagnostic outcome."""

    def test_corridor_a(self) -> None:
        m = load_manifest(FIXTURES / "corridor-a")
        obs = datasets.load_observations(m)

        # S1 nominal: fits clean, endpoints match the prediction.
        att, (u, v) = _span_uv(m, "S1", obs["S1"])
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK
        assert res.rms is not None and res.rms < profile.RMS_MAX_M
        assert (
            max(abs(d) for d in endpoint_deviations(res.params, att))
            < profile.ENDPOINT_TOLERANCE_M
        )  # type: ignore[index]

        # S2: the planted endpoint error is detected as an endpoint mismatch.
        att2, (u2, v2) = _span_uv(m, "S2", obs["S2"])
        res2 = fit_free(u2, v2, att2)
        assert res2.status == profile.FitStatus.OK
        dev = endpoint_deviations(res2.params, att2)  # type: ignore[arg-type]
        assert abs(dev[0]) < profile.ENDPOINT_TOLERANCE_M
        assert dev[1] > profile.ENDPOINT_TOLERANCE_M  # predicted 10.5 vs true 12.0

        # S2 corrected to the true candidate: constrained fit passes.
        pole3 = m.pole("P3")
        high = dict(pole3.attachment_candidates)["P3:high"]
        att_true = profile.Attachments(att2.u_a, att2.v_a, att2.u_b, high[2])
        corr = fit_constrained(u2, v2, att_true)
        assert corr.status == profile.FitStatus.OK
        assert corr.rms is not None and corr.rms < profile.RMS_MAX_M

        # S2 corrected to the low candidate: infeasible under the profile.
        low = dict(pole3.attachment_candidates)["P3:low"]
        att_bad = profile.Attachments(att2.u_a, att2.v_a, att2.u_b, low[2])
        infeasible = fit_constrained(u2, v2, att_bad)
        assert infeasible.status == profile.FitStatus.INFEASIBLE

        # S3 unequal heights: supported case fits clean.
        att3, (u3, v3) = _span_uv(m, "S3", obs["S3"])
        res3 = fit_free(u3, v3, att3)
        assert res3.status == profile.FitStatus.OK
        assert res3.rms is not None and res3.rms < profile.RMS_MAX_M

        # S4 noisy: fits but fails the residual quality gate.
        att4, (u4, v4) = _span_uv(m, "S4", obs["S4"])
        res4 = fit_free(u4, v4, att4)
        assert res4.status == profile.FitStatus.OK
        assert res4.rms is not None and res4.rms > profile.RMS_MAX_M

    def test_corridor_adverse_is_insufficient(self) -> None:
        m = load_manifest(FIXTURES / "corridor-adverse")
        obs = datasets.load_observations(m)
        for span_id, why in (("A1", "gap"), ("A2", "points")):
            att, (u, v) = _span_uv(m, span_id, obs[span_id])
            res = fit_free(u, v, att)
            assert res.status == profile.FitStatus.INSUFFICIENT_EVIDENCE
            assert res.reason is not None and why in res.reason

    def test_corridor_b_holdout_fits(self) -> None:
        m = load_manifest(FIXTURES / "corridor-b")
        assert m.role == "evaluation-holdout"
        ref = datasets.load_reference(m)
        truth = {s["span_id"]: s["truth"] for s in ref["spans"]}
        obs = datasets.load_observations(m)
        for span in m.spans:
            att, (u, v) = _span_uv(m, span.span_id, obs[span.span_id])
            res = fit_free(u, v, att)
            assert res.status == profile.FitStatus.OK, span.span_id
            t = truth[span.span_id]
            # Geometric fidelity is the honest metric: a is weakly identified
            # in some regimes, so compare curves over the span, not raw a.
            grid = np.linspace(0.0, att.length, 501)
            from cateniq.geometry.catenary import catenary_v

            err = float(
                np.abs(
                    catenary_v(grid, *res.params)  # type: ignore[arg-type]
                    - catenary_v(grid, t["u_v"], t["v_v"], t["a"])
                ).max()
            )
            assert err < 0.05, f"{span.span_id}: curve deviation {err:.3f} m"
            dev = endpoint_deviations(res.params, att)  # type: ignore[arg-type]
            assert max(abs(d) for d in dev) < profile.ENDPOINT_TOLERANCE_M
            assert res.rms is not None and res.rms < profile.RMS_MAX_M


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
