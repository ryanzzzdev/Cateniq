"""Bridge dataset records to the span-local fitting plane.

A span's vertical plane passes through its two attachment points. The plane
transform is explicit and reproducible: u is horizontal distance along the
plane direction from attachment A, v is world Z.
"""

from typing import Any

import numpy as np
import numpy.typing as npt

from cateniq.datasets.manifest import Manifest, ManifestError
from cateniq.geometry.profile import Attachments

F64 = npt.NDArray[np.float64]


def span_plane(
    manifest: Manifest, span_id: str, attach_a: Any, attach_b: Any
) -> tuple[Attachments, F64, F64]:
    """Return (attachments in plane coords, world origin, horizontal unit dir).

    attach_a/attach_b are world [x, y, z] points (declared or corrected). The
    returned Attachments place u_a=0 at attachment A and u_b=L at B.
    """
    a = np.asarray(attach_a, dtype=np.float64)
    b = np.asarray(attach_b, dtype=np.float64)
    if a.shape != (3,) or b.shape != (3,):
        raise ManifestError(f"{span_id}: attachments must be 3-vectors")
    d = b - a
    horiz = np.hypot(d[0], d[1])
    if horiz < 1e-9:
        raise ManifestError(f"{span_id}: attachments have no horizontal separation")
    plane_u = np.array([d[0] / horiz, d[1] / horiz])
    att = Attachments(0.0, float(a[2]), float(horiz), float(b[2]))
    return att, a, plane_u


def to_plane(xyz: F64, origin: F64, plane_u: F64) -> tuple[F64, F64]:
    """Project world points onto the span plane: u along-plane, v = world Z."""
    d = xyz[:, :2] - origin[:2]
    return d @ plane_u, xyz[:, 2].copy()


def predicted_plane(
    manifest: Manifest, predictions: dict[str, Any], span_id: str
) -> tuple[Attachments, F64, F64]:
    """Plane transform for a span's *predicted* attachments."""
    manifest.span(span_id)
    for sp in predictions["spans"]:
        if sp["span_id"] == span_id:
            return span_plane(manifest, span_id, sp["attach_a"], sp["attach_b"])
    raise ManifestError(f"predictions: no entry for span {span_id}")
