"""Corridor serving layer: dataset payloads and computed diagnostics.

Reads only fitter-facing assets (observations, predictions, context). The
evaluation/reference assets are never touched here.
"""

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

    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir
        self._manifests: dict[str, Manifest] = {}

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

    def _fit_for(self, m: Manifest, span_id: str) -> dict[str, Any]:
        preds = datasets.load_predictions(m)
        obs = datasets.load_observations(m)
        att, origin, plane_u = predicted_plane(m, preds, span_id)
        arr = obs[span_id]
        xyz = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
        u, v = to_plane(xyz, origin, plane_u)
        res = fit_free(u, v, att)
        issues: list[dict[str, Any]] = []
        dev: tuple[float, float] | None = None
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
            assert res.params is not None and res.rms is not None
            dev = endpoint_deviations(res.params, att)
            if res.rms > profile.RMS_MAX_M:
                issues.append(
                    {
                        "kind": "high_residual",
                        "detail": f"RMS {res.rms:.3f} m",
                        "threshold": f"RMS_MAX_M {profile.RMS_MAX_M}",
                    }
                )
            for which, d in (("a", dev[0]), ("b", dev[1])):
                if abs(d) > profile.ENDPOINT_TOLERANCE_M:
                    issues.append(
                        {
                            "kind": "endpoint_mismatch",
                            "detail": (
                                f"endpoint {which} deviates {d:+.3f} m from the "
                                f"predicted attachment"
                            ),
                            "threshold": (
                                f"ENDPOINT_TOLERANCE_M {profile.ENDPOINT_TOLERANCE_M}"
                            ),
                        }
                    )
        return {
            "span_id": span_id,
            "status": res.status.value,
            "basis": "prediction",
            "units": "m",
            "rms": res.rms,
            "p95": res.p95,
            "condition": res.condition,
            "endpoint_deviations": list(dev) if dev is not None else None,
            "issues": issues,
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
            }
        u, v = to_plane(xyz, origin, plane_u)
        res = fit_constrained(u, v, att)

        # Provenance: off-plane offset vs the *predicted* plane, and the
        # lateral observation scatter about the corrected plane.
        _pa, pred_origin, pred_u = predicted_plane(m, preds, span_id)
        pred_n = np.array([-pred_u[1], pred_u[0]])
        a_w = np.asarray(attach_a, dtype=np.float64)
        b_w = np.asarray(attach_b, dtype=np.float64)
        off_a = float((a_w[:2] - pred_origin[:2]) @ pred_n)
        off_b = float((b_w[:2] - pred_origin[:2]) @ pred_n)
        lat = (xyz[:, :2] - origin[:2]) @ np.array([-plane_u[1], plane_u[0]])
        constraints = {
            "attach_a": [float(x) for x in a_w],
            "attach_b": [float(x) for x in b_w],
            "off_plane_m": [off_a, off_b],
            "obs_lateral_rms_m": float(np.sqrt(np.mean(lat**2))),
        }

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
