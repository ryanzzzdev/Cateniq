"""Manifest schema, validation and asset loading (CAT-005).

Manifest identity is content-addressed: asset sha256 hashes take precedence
over friendly names. Validation rejects malformed structure, unsupported
schema versions, bad references, hash/count mismatches, non-finite
coordinates and duplicate point IDs before any fitting sees the data.
"""

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt

SCHEMA_VERSION = 1

# Observation labels (supplied inputs, never inferred).
LABEL_CONDUCTOR = 1
LABEL_POLE = 2
LABEL_CONTEXT = 3

OBS_DTYPE = np.dtype(
    [
        ("point_id", "<i8"),
        ("x", "<f8"),
        ("y", "<f8"),
        ("z", "<f8"),
        ("label", "<u1"),
    ]
)
F64 = npt.NDArray[np.float64]
ObsArray = npt.NDArray[np.void]


class ManifestError(ValueError):
    """Raised for any manifest, reference or asset validation failure."""


@dataclass(frozen=True)
class Pole:
    pole_id: str
    position: tuple[float, float, float]
    attachment_candidates: tuple[tuple[str, tuple[float, float, float]], ...]


@dataclass(frozen=True)
class Span:
    span_id: str
    pole_a: str
    pole_b: str


@dataclass(frozen=True)
class AssetRef:
    path: str
    sha256: str
    point_count: int | None = None
    span_id: str | None = None


@dataclass(frozen=True)
class Manifest:
    dataset_id: str
    role: str
    seed: int
    generator: dict[str, Any]
    coordinate_convention: dict[str, Any]
    poles: tuple[Pole, ...]
    spans: tuple[Span, ...]
    observations: tuple[AssetRef, ...]
    context: AssetRef | None
    predictions: AssetRef
    evaluation: AssetRef | None
    planted_errors: tuple[dict[str, Any], ...]
    root: Path

    def span(self, span_id: str) -> Span:
        for s in self.spans:
            if s.span_id == span_id:
                return s
        raise ManifestError(f"unknown span: {span_id}")

    def pole(self, pole_id: str) -> Pole:
        for p in self.poles:
            if p.pole_id == pole_id:
                return p
        raise ManifestError(f"unknown pole: {pole_id}")


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ManifestError(msg)


def _vec3(v: Any, what: str) -> tuple[float, float, float]:
    _check(isinstance(v, (list, tuple)) and len(v) == 3, f"{what}: expected 3-vector")
    t = (float(v[0]), float(v[1]), float(v[2]))
    _check(all(np.isfinite(t)), f"{what}: non-finite coordinate")
    return t


def _asset(raw: dict[str, Any], what: str) -> AssetRef:
    return AssetRef(
        path=str(raw["path"]),
        sha256=str(raw["sha256"]),
        point_count=int(raw["point_count"])
        if raw.get("point_count") is not None
        else None,
        span_id=str(raw["span_id"]) if raw.get("span_id") is not None else None,
    )


def load_manifest(dataset_dir: str | Path) -> Manifest:
    """Parse and structurally validate a manifest (asset bytes not yet read)."""
    root = Path(dataset_dir)
    raw = json.loads((root / "manifest.json").read_text())

    _check(raw.get("schema_version") == SCHEMA_VERSION, "unsupported schema_version")
    _check(bool(raw.get("dataset_id")), "missing dataset_id")
    cc = raw.get("coordinate_convention") or {}
    _check(cc.get("units") == "m", "unsupported units")
    _check(
        cc.get("axes") == "right-handed" and cc.get("up") == "+Z", "unsupported axes"
    )

    topo = raw.get("topology") or {}
    poles: list[Pole] = []
    seen_poles: set[str] = set()
    for pr in topo.get("poles", []):
        pid = str(pr["pole_id"])
        _check(
            pid != "" and pid not in seen_poles, f"duplicate or empty pole_id: {pid}"
        )
        seen_poles.add(pid)
        cands = tuple(
            (str(c["candidate_id"]), _vec3(c["point"], f"{pid} candidate"))
            for c in pr.get("attachment_candidates", [])
        )
        _check(
            len({c[0] for c in cands}) == len(cands), f"{pid}: duplicate candidate ids"
        )
        poles.append(Pole(pid, _vec3(pr["position"], f"{pid} position"), cands))

    spans: list[Span] = []
    seen_spans: set[str] = set()
    for sr in topo.get("spans", []):
        sid = str(sr["span_id"])
        _check(
            sid != "" and sid not in seen_spans, f"duplicate or empty span_id: {sid}"
        )
        seen_spans.add(sid)
        _check(
            sr["pole_a"] in seen_poles and sr["pole_b"] in seen_poles,
            f"{sid}: unknown pole reference",
        )
        _check(sr["pole_a"] != sr["pole_b"], f"{sid}: span between a pole and itself")
        spans.append(Span(sid, str(sr["pole_a"]), str(sr["pole_b"])))

    assets = raw.get("assets") or {}
    obs = tuple(_asset(a, "observation") for a in assets.get("observations", []))
    for a in obs:
        if a.span_id is not None:
            _check(
                a.span_id in seen_spans,
                f"observation asset references unknown span {a.span_id}",
            )
    context_raw = assets.get("context")
    context = _asset(context_raw, "context") if context_raw else None
    ev = assets.get("evaluation") or {}
    evaluation = (
        AssetRef(path=str(ev["reference"]), sha256=str(ev["sha256"])) if ev else None
    )

    return Manifest(
        dataset_id=str(raw["dataset_id"]),
        role=str(raw.get("role", "demo")),
        seed=int((raw.get("generator") or {})["seed"]),
        generator=dict(raw.get("generator") or {}),
        coordinate_convention=dict(cc),
        poles=tuple(poles),
        spans=tuple(spans),
        observations=obs,
        context=context,
        predictions=_asset(assets["predictions"], "predictions"),
        evaluation=evaluation,
        planted_errors=tuple(ev.get("planted_errors", [])),
        root=root,
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _verify_refs(manifest: Manifest, refs: list[AssetRef | None]) -> None:
    for ref in refs:
        if ref is None:
            continue
        path = manifest.root / ref.path
        _check(path.is_file(), f"missing asset {ref.path}")
        _check(_sha256(path) == ref.sha256, f"hash mismatch for {ref.path}")


def verify_assets(manifest: Manifest) -> None:
    """Verify every referenced asset exists and matches its recorded hash —
    including the evaluation section (full-dataset integrity check)."""
    _verify_refs(
        manifest,
        [
            *manifest.observations,
            manifest.predictions,
            manifest.evaluation,
            manifest.context,
        ],
    )


def verify_fitter_assets(manifest: Manifest) -> None:
    """Verify only the assets the fitting path reads. Never touches evaluation."""
    _verify_refs(
        manifest, [*manifest.observations, manifest.predictions, manifest.context]
    )


def _load_points(path: Path) -> ObsArray:
    arr = cast(ObsArray, np.load(path))
    _check(arr.dtype == OBS_DTYPE, f"{path.name}: unexpected dtype {arr.dtype}")
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
    _check(bool(np.isfinite(xyz).all()), f"{path.name}: non-finite coordinates")
    _check(
        len(np.unique(arr["point_id"])) == len(arr), f"{path.name}: duplicate point IDs"
    )
    return arr


def load_observations(manifest: Manifest) -> dict[str, ObsArray]:
    """Fitter-facing read: per-span conductor observations plus context.

    Never reads or verifies the evaluation section — see the module boundary
    rule in `cateniq.datasets`.
    """
    _verify_refs(manifest, [*manifest.observations, manifest.context])
    out: dict[str, ObsArray] = {}
    for ref in manifest.observations:
        if ref.span_id is None:
            continue
        arr = _load_points(manifest.root / ref.path)
        _check(len(arr) == (ref.point_count or len(arr)), f"{ref.path}: count mismatch")
        out[ref.span_id] = arr
    return out


def iter_span_points(manifest: Manifest) -> Iterator[tuple[str, ObsArray]]:
    yield from load_observations(manifest).items()


def load_context_points(manifest: Manifest) -> ObsArray | None:
    if manifest.context is None:
        return None
    return _load_points(manifest.root / manifest.context.path)


def load_predictions(manifest: Manifest) -> dict[str, Any]:
    """Original predicted geometry (predicted attachments and fit params)."""
    _verify_refs(manifest, [manifest.predictions])
    raw = json.loads((manifest.root / manifest.predictions.path).read_text())
    _check(
        raw.get("schema_version") == SCHEMA_VERSION, "predictions: bad schema_version"
    )
    _check(
        raw.get("dataset_id") == manifest.dataset_id, "predictions: dataset mismatch"
    )
    known = {s.span_id for s in manifest.spans}
    for sp in raw.get("spans", []):
        _check(sp["span_id"] in known, f"predictions: unknown span {sp['span_id']}")
        _vec3(sp["attach_a"], "attach_a")
        _vec3(sp["attach_b"], "attach_b")
    return cast(dict[str, Any], raw)


def load_reference(manifest: Manifest) -> dict[str, Any]:
    """Evaluation-only reference truth. Never call from the fitting path."""
    if manifest.evaluation is None:
        raise ManifestError("dataset has no evaluation section")
    raw = json.loads((manifest.root / manifest.evaluation.path).read_text())
    _check(raw.get("schema_version") == SCHEMA_VERSION, "reference: bad schema_version")
    _check(raw.get("dataset_id") == manifest.dataset_id, "reference: dataset mismatch")
    return cast(dict[str, Any], raw)
