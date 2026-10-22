// Pure interaction math for the endpoint editor — no three.js imports so the
// logic is unit-testable in vitest and the e2e spec asserts world coordinates.
import type { Candidate, Vec3 } from "./api";

export type { Vec3 };

export interface SpanPlane {
  origin: Vec3;
  /** Horizontal unit direction from attach A to attach B (x,y components). */
  u: [number, number];
  /** Plane normal (horizontal, perpendicular to u). */
  normal: Vec3;
}

/** The declared vertical plane through a span's two attachments. */
export function spanPlane(a: Vec3, b: Vec3): SpanPlane {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const horiz = Math.hypot(dx, dy);
  if (horiz < 1e-9) throw new Error("attachments have no horizontal separation");
  const ux = dx / horiz;
  const uy = dy / horiz;
  // normal = u cross z-up direction
  return { origin: [...a], u: [ux, uy], normal: [uy, -ux, 0] };
}

/** Intersect a world-space ray with the span plane. Null if parallel. */
export function rayPlanePoint(
  rayOrigin: Vec3,
  rayDir: Vec3,
  plane: SpanPlane,
): Vec3 | null {
  const denom =
    rayDir[0] * plane.normal[0] +
    rayDir[1] * plane.normal[1] +
    rayDir[2] * plane.normal[2];
  if (Math.abs(denom) < 1e-12) return null;
  const t =
    ((plane.origin[0] - rayOrigin[0]) * plane.normal[0] +
      (plane.origin[1] - rayOrigin[1]) * plane.normal[1] +
      (plane.origin[2] - rayOrigin[2]) * plane.normal[2]) /
    denom;
  if (t <= 0) return null;
  return [
    rayOrigin[0] + rayDir[0] * t,
    rayOrigin[1] + rayDir[1] * t,
    rayOrigin[2] + rayDir[2] * t,
  ];
}

/** Nearest candidate within `radius` metres of `point`, or null. */
export function snapToCandidate(
  point: Vec3,
  candidates: Candidate[],
  radius: number,
): Candidate | null {
  let best: Candidate | null = null;
  let bestD = radius;
  for (const c of candidates) {
    const d = Math.hypot(
      point[0] - c.point[0],
      point[1] - c.point[1],
      point[2] - c.point[2],
    );
    if (d < bestD) {
      best = c;
      bestD = d;
    }
  }
  return best;
}

/** Mirror of the frozen profile: v(u) = v_v + a(cosh((u−u_v)/a) − 1). */
export function catenaryV(u: number, u_v: number, v_v: number, a: number): number {
  const s = Math.sinh((u - u_v) / (2 * a));
  return v_v + 2 * a * s * s;
}

/** Sample the predicted/fitted curve into world points. */
export function catenaryWorldPoints(
  attachA: Vec3,
  attachB: Vec3,
  params: { u_v: number; v_v: number; a: number },
  samples = 129,
): Vec3[] {
  const plane = spanPlane(attachA, attachB);
  const length = Math.hypot(attachB[0] - attachA[0], attachB[1] - attachA[1]);
  const pts: Vec3[] = [];
  for (let i = 0; i < samples; i++) {
    const u = (length * i) / (samples - 1);
    const v = catenaryV(u, params.u_v, params.v_v, params.a);
    pts.push([
      plane.origin[0] + plane.u[0] * u,
      plane.origin[1] + plane.u[1] * u,
      v,
    ]);
  }
  return pts;
}

export function displacement(from: Vec3, to: Vec3): number {
  return Math.hypot(to[0] - from[0], to[1] - from[1], to[2] - from[2]);
}
