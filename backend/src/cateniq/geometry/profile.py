"""Frozen numerical profile for conductor fitting (CAT-004 / BLK-001).

These constants are the contract between the dataset fixtures, the fitter and
the diagnostics. The fitting reference implementation in
`cateniq.geometry.catenary` exists to validate this profile; CAT-007 builds the
production fitter on the same contracts. Values were frozen against the
independently derived reference cases in `backend/tests/test_geometry_profile.py`
— see docs/project/evidence/geometry-profile.md for the measured evidence.

Coordinate conventions: span-local 2D coordinates (u, v). u is horizontal
distance in metres along the span's vertical plane from the first support
attachment toward the second; v is height in metres (world Z). A span occupies
u in [0, L]. World (x, y, z) to plane (u, v) transforms are defined in the
dataset contract.
"""

from dataclasses import dataclass
from enum import Enum

# --- Supported domain -------------------------------------------------------
# One conductor per span in a declared vertical plane. Spans outside these
# bounds are rejected as unsupported rather than silently forced into the model.
SPAN_MIN_M: float = 10.0
SPAN_MAX_M: float = 120.0

# Catenary parameter a = H/w (horizontal tension per unit weight), metres.
# a < ~3 m implies sag beyond the supported model for typical spans; a above
# ~5000 m is indistinguishable from a straight line at observation noise.
A_MIN: float = 3.0
A_MAX: float = 5000.0

# Maximum sag (vertex dip below the chord) as a fraction of span length.
# Beyond ~0.2 the single-plane slack-conductor model is not our supported case.
MAX_SAG_FRACTION: float = 0.20

# --- Evidence requirements --------------------------------------------------
# A fit may not be reported without these; failure -> INSUFFICIENT_EVIDENCE.
MIN_POINTS: int = 30
# Fraction of the span extent [0, L] covered by observations (u_max - u_min)/L.
MIN_COVERAGE: float = 0.60
# Largest horizontal observation gap as a fraction of L; a larger gap means the
# middle of the conductor is unobserved and the curve is unconstrained there.
MAX_GAP_FRACTION: float = 0.25
# Note: no vertex-bracketing requirement — a legitimately unequal-height span
# can place the vertex outside the observed extent (monotonic conductor), and
# rejecting it would break a supported case. Identifiability risk is bounded by
# COND_MAX and the A range instead.

# --- Fit outcome and diagnostic thresholds -----------------------------------
RMS_MAX_M: float = 0.15  # nominal fit RMS residual ceiling
RESIDUAL_P95_MAX_M: float = 0.30  # 95th-percentile absolute residual ceiling
# |fitted endpoint height - declared attachment| above which an endpoint
# mismatch diagnostic is raised.
ENDPOINT_TOLERANCE_M: float = 0.50
# Jacobian condition number above which a successful least-squares result is
# reported UNSTABLE rather than silently trusted.
COND_MAX: float = 1.0e10


class FitStatus(Enum):
    """Result classification for a single span fit."""

    OK = "ok"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"
    INFEASIBLE = "infeasible"
    # Inputs or evidence describe a span outside the supported domain —
    # reported, never silently forced into the model.
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Attachments:
    """Declared endpoint coordinates in span-local (u, v), u_a < u_b."""

    u_a: float
    v_a: float
    u_b: float
    v_b: float

    @property
    def length(self) -> float:
        return self.u_b - self.u_a


@dataclass(frozen=True)
class FitResult:
    """Outcome of fitting one span. `params` is (u_v, v_v, a) when present."""

    status: FitStatus
    params: tuple[float, float, float] | None
    rms: float | None
    p95: float | None
    condition: float | None
    reason: str | None
