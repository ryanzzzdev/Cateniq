"""Deterministic corridor fixture generation (CAT-005).

Generates small immutable datasets under `fixtures/`: observations (labelled
point assets), predictions (the extraction output under review, including any
declared planted error) and evaluation-only reference truth. All randomness
flows through seeded generators; regenerating the same spec yields
byte-identical assets.

True geometry lives only in `evaluation/reference.json`; the planted error is
declared in the manifest's evaluation section. The fitter-facing load path
never reads it.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from cateniq.datasets.manifest import (
    LABEL_CONDUCTOR,
    LABEL_CONTEXT,
    LABEL_POLE,
    OBS_DTYPE,
    SCHEMA_VERSION,
)
from cateniq.geometry.catenary import catenary_v, vertex_from_endpoints
from cateniq.geometry.profile import Attachments

GENERATOR_NAME = "cateniq.datasets.gen"
GENERATOR_VERSION = 1


@dataclass(frozen=True)
class PoleSpec:
    pole_id: str
    x: float  # corridor runs along +x, conductor planes at y = 0
    top_z: float
    candidates: tuple[tuple[str, float], ...]  # (name, attachment height z)


@dataclass(frozen=True)
class SpanSpec:
    span_id: str
    pole_a: str
    pole_b: str
    attach_a: str  # true attachment candidate names on each pole
    attach_b: str
    a: float  # true catenary constant (m)
    sigma: float  # vertical observation noise (m)
    n: int  # observation count
    # Declared planted prediction error: predictions use this candidate name
    # on pole_b instead of the true attach_b.
    predicted_b: str | None = None
    # Observation sampling windows as fractions of span length.
    u_windows: tuple[tuple[float, float], ...] = ((0.0, 1.0),)


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    seed: int
    role: str  # "demo" or "evaluation-holdout"
    poles: tuple[PoleSpec, ...]
    spans: tuple[SpanSpec, ...]


def _structured(n: int) -> npt.NDArray[np.void]:
    return np.zeros(n, dtype=OBS_DTYPE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_point(pole: PoleSpec, name: str) -> list[float]:
    z = dict(pole.candidates)[name]
    return [pole.x, 0.0, z]


def _span_points(
    spec_s: SpanSpec,
    att: Attachments,
    u_v: float,
    v_v: float,
    x_origin: float,
    rng: np.random.Generator,
    ids: npt.NDArray[np.int64],
) -> npt.NDArray[np.void]:
    n = spec_s.n
    windows = np.asarray(spec_s.u_windows, dtype=np.float64)
    weights = windows[:, 1] - windows[:, 0]
    counts = np.floor(weights / weights.sum() * n).astype(int)
    counts[-1] += n - int(counts.sum())
    length = att.length
    u = np.concatenate(
        [
            rng.uniform(lo * length, hi * length, int(c))
            for (lo, hi), c in zip(windows, counts, strict=True)
        ]
    )
    v = catenary_v(u, u_v, v_v, spec_s.a)
    arr = _structured(n)
    arr["point_id"] = ids
    arr["x"] = x_origin + u
    arr["y"] = rng.normal(0.0, spec_s.sigma / 3.0, n)  # lateral scatter for realism
    arr["z"] = v + rng.normal(0.0, spec_s.sigma, n)
    arr["label"] = LABEL_CONDUCTOR
    return arr


def _context_points(
    spec: DatasetSpec, rng: np.random.Generator, next_id: int
) -> tuple[npt.NDArray[np.void], int]:
    parts: list[npt.NDArray[np.void]] = []
    for p in spec.poles:
        k = 60
        arr = _structured(k)
        arr["point_id"] = np.arange(next_id, next_id + k)
        next_id += k
        arr["x"] = p.x + rng.normal(0.0, 0.15, k)
        arr["y"] = rng.normal(0.0, 0.15, k)
        arr["z"] = rng.uniform(0.0, p.top_z, k)
        arr["label"] = LABEL_POLE
        parts.append(arr)
    g = 600
    arr = _structured(g)
    arr["point_id"] = np.arange(next_id, next_id + g)
    next_id += g
    xs = [p.x for p in spec.poles]
    arr["x"] = rng.uniform(min(xs) - 10.0, max(xs) + 10.0, g)
    arr["y"] = rng.uniform(-15.0, 15.0, g)
    arr["z"] = rng.uniform(-0.3, 0.3, g)
    arr["label"] = LABEL_CONTEXT
    parts.append(arr)
    return np.concatenate(parts), next_id


def generate_dataset(out_root: str | Path, spec: DatasetSpec) -> Path:
    """Write a complete fixture dataset; returns the dataset directory."""
    root = Path(out_root) / spec.dataset_id
    obs_dir = root / "observations"
    obs_dir.mkdir(parents=True, exist_ok=True)
    (root / "evaluation").mkdir(exist_ok=True)
    (root / "predictions").mkdir(exist_ok=True)

    rng = np.random.default_rng(spec.seed)
    poles = {p.pole_id: p for p in spec.poles}

    next_id = 1
    obs_refs: list[dict[str, Any]] = []
    pred_spans: list[dict[str, Any]] = []
    ref_spans: list[dict[str, Any]] = []
    planted: list[dict[str, Any]] = []

    for s in spec.spans:
        pa, pb = poles[s.pole_a], poles[s.pole_b]
        a_pt = _candidate_point(pa, s.attach_a)
        b_pt = _candidate_point(pb, s.attach_b)
        att = Attachments(0.0, a_pt[2], pb.x - pa.x, b_pt[2])
        u_v, v_v = vertex_from_endpoints(att, s.a)
        ids = np.arange(next_id, next_id + s.n)
        next_id += s.n
        arr = _span_points(s, att, u_v, v_v, pa.x, rng, ids)
        path = obs_dir / f"{s.span_id}.npy"
        np.save(path, arr)
        obs_refs.append(
            {
                "span_id": s.span_id,
                "path": f"observations/{s.span_id}.npy",
                "sha256": _sha256(path),
                "point_count": s.n,
            }
        )

        # Prediction: a planted error replaces the true attach_b candidate.
        pred_b = _candidate_point(pb, s.predicted_b or s.attach_b)
        pred_att = Attachments(0.0, a_pt[2], pb.x - pa.x, pred_b[2])
        p_u_v, p_v_v = vertex_from_endpoints(pred_att, s.a)
        pred_spans.append(
            {
                "span_id": s.span_id,
                "attach_a": a_pt,
                "attach_b": pred_b,
                "params": {"u_v": p_u_v, "v_v": p_v_v, "a": s.a},
                "plane_u": [1.0, 0.0],
            }
        )
        ref_spans.append(
            {
                "span_id": s.span_id,
                "truth": {
                    "attach_a": a_pt,
                    "attach_b": b_pt,
                    "u_v": u_v,
                    "v_v": v_v,
                    "a": s.a,
                },
                "sigma": s.sigma,
                "n": s.n,
            }
        )
        if s.predicted_b:
            planted.append(
                {
                    "span_id": s.span_id,
                    "kind": "endpoint-displacement",
                    "true_candidate": f"{pb.pole_id}:{s.attach_b}",
                    "predicted_candidate": f"{pb.pole_id}:{s.predicted_b}",
                }
            )

    ctx, next_id = _context_points(spec, rng, next_id)
    ctx_path = obs_dir / "context.npy"
    np.save(ctx_path, ctx)
    ctx_ref = {
        "path": "observations/context.npy",
        "sha256": _sha256(ctx_path),
        "point_count": len(ctx),
    }

    pred_path = root / "predictions" / "predictions.json"
    pred_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": spec.dataset_id,
                "spans": pred_spans,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    ref_path = root / "evaluation" / "reference.json"
    ref_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": spec.dataset_id,
                "spans": ref_spans,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": spec.dataset_id,
        "role": spec.role,
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
            "seed": spec.seed,
        },
        "coordinate_convention": {
            "units": "m",
            "axes": "right-handed",
            "up": "+Z",
            "origin": [0.0, 0.0, 0.0],
        },
        "topology": {
            "poles": [
                {
                    "pole_id": p.pole_id,
                    "position": [p.x, 0.0, 0.0],
                    "attachment_candidates": [
                        {
                            "candidate_id": f"{p.pole_id}:{name}",
                            "point": _candidate_point(p, name),
                        }
                        for name, _z in p.candidates
                    ],
                }
                for p in spec.poles
            ],
            "spans": [
                {"span_id": s.span_id, "pole_a": s.pole_a, "pole_b": s.pole_b}
                for s in spec.spans
            ],
        },
        "assets": {
            "observations": obs_refs,
            "context": ctx_ref,
            "predictions": {
                "path": "predictions/predictions.json",
                "sha256": _sha256(pred_path),
            },
            "evaluation": {
                "reference": "evaluation/reference.json",
                "sha256": _sha256(ref_path),
                "planted_errors": planted,
            },
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return root
