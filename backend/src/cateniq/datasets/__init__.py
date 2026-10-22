"""Dataset manifests, validation and fixture loading.

Boundary rule (dataset contract): `load_observations` / `iter_span_points` are
the fitter-facing reads and never touch the `evaluation` section. Reference
truth and planted-error declarations are only reachable through
`load_reference`, reserved for tests and explicit evaluation views.
"""

from cateniq.datasets.manifest import (
    LABEL_CONDUCTOR,
    LABEL_CONTEXT,
    LABEL_POLE,
    Manifest,
    ManifestError,
    Pole,
    Span,
    iter_span_points,
    load_context_points,
    load_manifest,
    load_observations,
    load_predictions,
    load_reference,
    verify_assets,
    verify_fitter_assets,
)
from cateniq.datasets.plane import predicted_plane, span_plane, to_plane

__all__ = [
    "LABEL_CONDUCTOR",
    "LABEL_CONTEXT",
    "LABEL_POLE",
    "Manifest",
    "ManifestError",
    "Pole",
    "Span",
    "iter_span_points",
    "load_context_points",
    "load_manifest",
    "load_observations",
    "load_predictions",
    "load_reference",
    "predicted_plane",
    "span_plane",
    "to_plane",
    "verify_assets",
    "verify_fitter_assets",
]
