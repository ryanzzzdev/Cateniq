"""Corridor serving layer: dataset payloads, computed diagnostics and the
durable review lifecycle (CAT-009).

Reads only fitter-facing assets (observations, predictions, context). The
evaluation/reference assets are never touched here.
"""

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from cateniq import datasets
from cateniq.datasets.manifest import (
    SCHEMA_VERSION,
    Manifest,
    ManifestError,
    ObsArray,
)
from cateniq.datasets.plane import predicted_plane, span_plane, to_plane
from cateniq.geometry import profile
from cateniq.geometry.catenary import (
    catenary_v,
    endpoint_deviations,
    fit_constrained,
    fit_free,
)
from cateniq.store import (
    ALGORITHM,
    MAX_EDITED_ENDPOINTS,
    ReviewStore,
    ValidationError,
)


def _columns(arr: ObsArray) -> dict[str, Any]:
    return {
        "point_id": arr["point_id"].tolist(),
        "x": arr["x"].tolist(),
        "y": arr["y"].tolist(),
        "z": arr["z"].tolist(),
        "label": arr["label"].tolist(),
    }


class CorridorService:
    """Serves datasets and diagnostics from a fixtures directory."""

    def __init__(self, fixtures_dir: Path, db_path: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir
        self._manifests: dict[str, Manifest] = {}
        self.store = ReviewStore(
            db_path if db_path is not None else fixtures_dir.parent / "reviews.db"
        )

    def _manifest(self, dataset_id: str) -> Manifest:
        if dataset_id not in self._manifests:
            self._manifests[dataset_id] = datasets.load_manifest(
                self.fixtures_dir / dataset_id
            )
        return self._manifests[dataset_id]

    def list_datasets(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.fixtures_dir.iterdir()):
            if not (path / "manifest.json").is_file():
                continue
            m = self._manifest(path.name)
            out.append(
                {
                    "dataset_id": m.dataset_id,
                    "role": m.role,
                    "span_count": len(m.spans),
                    "point_count": sum(
                        a.point_count or 0
                        for a in (*m.observations, m.context)
                        if a is not None
                    ),
                }
            )
        return out

    def dataset(self, dataset_id: str) -> dict[str, Any]:
        m = self._manifest(dataset_id)
        obs = datasets.load_observations(m)
        preds = datasets.load_predictions(m)
        return {
            "dataset_id": m.dataset_id,
            "role": m.role,
            "schema_version": SCHEMA_VERSION,
            "generator": m.generator,
            "coordinate_convention": m.coordinate_convention,
            "poles": [
                {
                    "pole_id": p.pole_id,
                    "position": list(p.position),
                    "attachment_candidates": [
                        {"candidate_id": cid, "point": list(pt)}
                        for cid, pt in p.attachment_candidates
                    ],
                }
                for p in m.poles
            ],
            "spans": [
                {"span_id": s.span_id, "pole_a": s.pole_a, "pole_b": s.pole_b}
                for s in m.spans
            ],
            "predictions": {
                sp["span_id"]: {
                    "attach_a": sp["attach_a"],
                    "attach_b": sp["attach_b"],
                    "params": sp["params"],
                    "plane_u": sp["plane_u"],
                }
                for sp in preds["spans"]
            },
            "observations": {sid: _columns(arr) for sid, arr in obs.items()},
            "context": (
                _columns(ctx)
                if (ctx := datasets.load_context_points(m)) is not None
                else None
            ),
        }

    @staticmethod
    def _issues(res: profile.FitResult, att: Any | None = None) -> list[dict[str, Any]]:
        """Validation issues for a fit result, solver status kept distinct.

        Applies the frozen quality gates to both prediction and corrected
        results; `att` enables the endpoint-mismatch check, which is only
        meaningful for a free fit against declared attachments.
        """
        issues: list[dict[str, Any]] = []
        if res.status == profile.FitStatus.INSUFFICIENT_EVIDENCE:
            issues.append(
                {
                    "kind": "insufficient_evidence",
                    "detail": res.reason,
                    "threshold": "frozen evidence gates",
                }
            )
        elif res.status == profile.FitStatus.UNSUPPORTED:
            issues.append(
                {
                    "kind": "unsupported_domain",
                    "detail": res.reason,
                    "threshold": "frozen domain bounds",
                }
            )
        elif res.status != profile.FitStatus.OK:
            issues.append(
                {
                    "kind": "fit_failed",
                    "detail": res.reason,
                    "threshold": "solver checks",
                }
            )
        else:
            if res.rms is not None and res.rms > profile.RMS_MAX_M:
                issues.append(
                    {
                        "kind": "high_residual",
                        "detail": f"RMS {res.rms:.3f} m",
                        "threshold": f"RMS_MAX_M {profile.RMS_MAX_M}",
                    }
                )
            if res.p95 is not None and res.p95 > profile.RESIDUAL_P95_MAX_M:
                issues.append(
                    {
                        "kind": "high_residual_p95",
                        "detail": f"residual p95 {res.p95:.3f} m",
                        "threshold": f"RESIDUAL_P95_MAX_M {profile.RESIDUAL_P95_MAX_M}",
                    }
                )
            if att is not None:
                assert res.params is not None
                for which, d in zip(
                    ("a", "b"), endpoint_deviations(res.params, att), strict=True
                ):
                    if abs(d) > profile.ENDPOINT_TOLERANCE_M:
                        issues.append(
                            {
                                "kind": "endpoint_mismatch",
                                "detail": (
                                    f"endpoint {which} deviates {d:+.3f} m "
                                    f"from the predicted attachment"
                                ),
                                "threshold": (
                                    "ENDPOINT_TOLERANCE_M "
                                    f"{profile.ENDPOINT_TOLERANCE_M}"
                                ),
                            }
                        )
        return issues

    def _fit_for(self, m: Manifest, span_id: str) -> dict[str, Any]:
        preds = datasets.load_predictions(m)
        obs = datasets.load_observations(m)
        att, origin, plane_u = predicted_plane(m, preds, span_id)
        arr = obs[span_id]
        xyz = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
        u, v = to_plane(xyz, origin, plane_u)
        res = fit_free(u, v, att)
        dev = None
        if res.status == profile.FitStatus.OK and res.params is not None:
            dev = endpoint_deviations(res.params, att)
        return {
            "span_id": span_id,
            "status": res.status.value,
            "basis": "prediction",
            "units": "m",
            "rms": res.rms,
            "p95": res.p95,
            "condition": res.condition,
            "endpoint_deviations": list(dev) if dev is not None else None,
            "issues": self._issues(res, att),
        }

    def diagnostics(self, dataset_id: str) -> dict[str, Any]:
        m = self._manifest(dataset_id)
        results = [self._fit_for(m, s.span_id) for s in m.spans]
        return {
            "dataset_id": dataset_id,
            "spans": results,
            "issue_count": sum(len(r["issues"]) for r in results),
        }

    def constrained_fit(
        self,
        dataset_id: str,
        span_id: str,
        attach_a: list[float],
        attach_b: list[float],
    ) -> dict[str, Any]:
        """Refit a span with corrected attachments; validation preview only.

        The corrected endpoints define the refit plane — they are never
        projected back into the predicted plane. Provenance reports how far
        each corrected endpoint lies off the predicted plane and the lateral
        scatter of observations about the corrected plane.
        """
        m = self._manifest(dataset_id)
        obs = datasets.load_observations(m)
        preds = datasets.load_predictions(m)
        arr = obs[span_id]
        xyz = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
        try:
            att, origin, plane_u = span_plane(m, span_id, attach_a, attach_b)
        except ManifestError as exc:
            return {
                "span_id": span_id,
                "status": profile.FitStatus.UNSUPPORTED.value,
                "basis": "corrected",
                "units": "m",
                "rms": None,
                "p95": None,
                "reason": str(exc),
                "fit": None,
                "constraints": None,
                "issues": [
                    {
                        "kind": "unsupported_domain",
                        "detail": str(exc),
                        "threshold": "frozen domain bounds",
                    }
                ],
            }
        u, v = to_plane(xyz, origin, plane_u)

        # Provenance: off-plane offset vs the *predicted* plane, and the
        # lateral observation scatter about the corrected plane.
        _pa, pred_origin, pred_u = predicted_plane(m, preds, span_id)
        pred_n = np.array([-pred_u[1], pred_u[0]])
        a_w = np.asarray(attach_a, dtype=np.float64)
        b_w = np.asarray(attach_b, dtype=np.float64)
        off_a = float((a_w[:2] - pred_origin[:2]) @ pred_n)
        off_b = float((b_w[:2] - pred_origin[:2]) @ pred_n)
        lat = (xyz[:, :2] - origin[:2]) @ np.array([-plane_u[1], plane_u[0]])
        lat_rms = float(np.sqrt(np.mean(lat**2)))
        constraints = {
            "attach_a": [float(x) for x in a_w],
            "attach_b": [float(x) for x in b_w],
            "off_plane_m": [off_a, off_b],
            "obs_lateral_rms_m": lat_rms,
        }

        # Support gate: the corrected plane must pass through the evidence.
        # A plane that leaves the observations metres to its side is
        # non-coplanar with the conductor — rejected, never silently fitted.
        if lat_rms > profile.LATERAL_TOLERANCE_M:
            reason = (
                f"corrected plane unsupported by observations: lateral RMS "
                f"{lat_rms:.3f} m > LATERAL_TOLERANCE_M {profile.LATERAL_TOLERANCE_M}"
            )
            res = profile.FitResult(
                profile.FitStatus.UNSUPPORTED, None, None, None, None, reason
            )
            return {
                "span_id": span_id,
                "status": res.status.value,
                "basis": "corrected",
                "units": "m",
                "rms": None,
                "p95": None,
                "reason": reason,
                "fit": None,
                "constraints": constraints,
                "issues": self._issues(res),
            }

        res = fit_constrained(u, v, att)
        params_world = None
        if res.params is not None:
            # Sample the fitted curve back into world coordinates for display.
            grid = np.linspace(att.u_a, att.u_b, 129)
            vv = catenary_v(grid, *res.params)
            params_world = {
                "u_v": res.params[0],
                "v_v": res.params[1],
                "a": res.params[2],
                "curve": [
                    [
                        float(origin[0] + plane_u[0] * uu),
                        float(origin[1] + plane_u[1] * uu),
                        float(vz),
                    ]
                    for uu, vz in zip(grid, vv, strict=True)
                ],
            }
        return {
            "span_id": span_id,
            "status": res.status.value,
            "basis": "corrected",
            "units": "m",
            "rms": res.rms,
            "p95": res.p95,
            "reason": res.reason,
            "fit": params_world,
            "constraints": constraints,
            "issues": self._issues(res),
        }

    def refit(
        self, dataset_id: str, edits: dict[str, dict[str, list[float]]]
    ) -> dict[str, Any]:
        """Full-corridor rerun: constrained where corrected, free elsewhere.

        Every span is recomputed; the result carries per-span `basis` so
        original and corrected results stay distinguishable.
        """
        m = self._manifest(dataset_id)
        results: list[dict[str, Any]] = []
        for s in m.spans:
            edit = edits.get(s.span_id)
            if edit is None:
                results.append(self._fit_for(m, s.span_id))
            else:
                results.append(
                    self.constrained_fit(
                        dataset_id,
                        s.span_id,
                        edit["attach_a"],
                        edit["attach_b"],
                    )
                )
        return {
            "dataset_id": dataset_id,
            "spans": results,
            "issue_count": sum(len(r.get("issues", [])) for r in results),
        }

    # -- durable review lifecycle (CAT-009) -----------------------------------

    def _manifest_hash(self, dataset_id: str) -> str:
        self._manifest(dataset_id)  # validates the manifest first
        h = hashlib.sha256()
        h.update((self.fixtures_dir / dataset_id / "manifest.json").read_bytes())
        return h.hexdigest()

    def _validate_edits(
        self, m: Manifest, edits: dict[str, Any]
    ) -> dict[str, dict[str, list[float]]]:
        """Operation payload checks: known spans, finite 3-vectors, bounded
        count. The full effective constraint set is stored, not a delta."""
        if not isinstance(edits, dict):
            raise ValidationError("edits must be a span-keyed mapping")
        span_ids = {s.span_id for s in m.spans}
        out: dict[str, dict[str, list[float]]] = {}
        count = 0
        for sid, e in edits.items():
            if sid not in span_ids:
                raise ValidationError(f"unknown span {sid}")
            if set(e) != {"attach_a", "attach_b"}:
                raise ValidationError(f"{sid}: edits need attach_a/attach_b")
            row: dict[str, list[float]] = {}
            for k in ("attach_a", "attach_b"):
                v = e[k]
                if (
                    not isinstance(v, list)
                    or len(v) != 3
                    or not all(isinstance(x, int | float) and np.isfinite(x) for x in v)
                ):
                    raise ValidationError(f"{sid}: {k} must be a finite 3-vector")
                row[k] = [float(x) for x in v]
            out[sid] = row
            count += 2
        if count > MAX_EDITED_ENDPOINTS:
            raise ValidationError(
                f"operation edits {count} endpoints > {MAX_EDITED_ENDPOINTS}"
            )
        return out

    def review_state(self, dataset_id: str) -> dict[str, Any]:
        return self.store.review(dataset_id, self._manifest_hash(dataset_id))

    def save_operation(
        self,
        dataset_id: str,
        operation_id: str,
        base_revision: int,
        edits: dict[str, Any],
    ) -> dict[str, Any]:
        m = self._manifest(dataset_id)
        self.review_state(dataset_id)  # ensures the review exists
        return self.store.save(
            dataset_id,
            operation_id,
            base_revision,
            self._validate_edits(m, edits),
        )

    def export_review(self, dataset_id: str) -> dict[str, Any]:
        """Schema-versioned snapshot of the review's durable state."""
        m = self._manifest(dataset_id)
        state = self.review_state(dataset_id)
        return {
            "schema_version": 1,
            "dataset": {
                "dataset_id": m.dataset_id,
                "manifest_hash": state["manifest_hash"],
                "coordinate_convention": m.coordinate_convention,
                "generator": m.generator,
            },
            "algorithm": {
                "name": ALGORITHM,
                "profile": {
                    "rms_max_m": profile.RMS_MAX_M,
                    "residual_p95_max_m": profile.RESIDUAL_P95_MAX_M,
                    "endpoint_tolerance_m": profile.ENDPOINT_TOLERANCE_M,
                    "lateral_tolerance_m": profile.LATERAL_TOLERANCE_M,
                },
            },
            "revision": state["revision"],
            "operations": self.store.history(dataset_id),
            "constraints": state["constraints"],
            "accepted": state["accepted"],
            "validation": self.store.current_validation(dataset_id),
        }

    def verify_export(self, export: dict[str, Any]) -> dict[str, Any]:
        """Reconstruct the effective constraint set from the exported
        operation history and check every referenced identity."""
        if export.get("schema_version") != 1:
            raise ValidationError("unsupported export schema_version")
        ds = export.get("dataset", {})
        dataset_id = ds.get("dataset_id")
        m = self._manifest(dataset_id)  # unknown dataset -> ManifestError
        if ds.get("manifest_hash") != self._manifest_hash(dataset_id):
            raise ValidationError("export dataset identity does not match")
        span_ids = {s.span_id for s in m.spans}
        ops = export.get("operations", [])
        prev_result = 0
        reconstructed: dict[str, Any] = {}
        for op in ops:
            if op["base_revision"] != prev_result:
                raise ValidationError(f"operation chain broken at seq {op['seq']}")
            for sid in op["payload"]["edits"]:
                if sid not in span_ids:
                    raise ValidationError(f"unknown span reference {sid}")
            reconstructed = op["payload"]["edits"]
            prev_result = op["result_revision"]
        if reconstructed != export.get("constraints", {}):
            raise ValidationError(
                "reconstructed constraints differ from declared export"
            )
        if prev_result != export.get("revision"):
            raise ValidationError("operation chain does not reach declared revision")
        return {
            "ok": True,
            "dataset_id": dataset_id,
            "revision": export["revision"],
            "constraints": reconstructed,
        }
