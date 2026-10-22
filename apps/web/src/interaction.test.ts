import { describe, expect, it } from "vitest";
import {
  catenaryWorldPoints,
  displacement,
  rayPlanePoint,
  snapToCandidate,
  spanPlane,
} from "./interaction";

const A: [number, number, number] = [50, 0, 12];
const B: [number, number, number] = [95, 0, 12];

describe("spanPlane", () => {
  it("builds the vertical plane through the attachments", () => {
    const p = spanPlane(A, B);
    expect(p.u[0]).toBeCloseTo(1);
    expect(p.u[1]).toBeCloseTo(0);
    expect(p.normal).toEqual([0, -1, 0]); // normal is horizontal, ±y
  });

  it("rejects coincident horizontal attachments", () => {
    expect(() => spanPlane([1, 2, 5], [1, 2, 9])).toThrow();
  });
});

describe("rayPlanePoint", () => {
  it("returns the ray/plane intersection", () => {
    const plane = spanPlane(A, B);
    const hit = rayPlanePoint([70, -30, 12], [0, 1, 0], plane);
    expect(hit).not.toBeNull();
    expect(hit![0]).toBeCloseTo(70);
    expect(hit![1]).toBeCloseTo(0);
    expect(hit![2]).toBeCloseTo(12);
  });

  it("returns null for a ray parallel to the plane", () => {
    const plane = spanPlane(A, B);
    expect(rayPlanePoint([70, -30, 12], [0, 0, 1], plane)).toBeNull();
  });

  it("returns null for a ray pointing away", () => {
    const plane = spanPlane(A, B);
    expect(rayPlanePoint([70, -30, 12], [0, -1, 0], plane)).toBeNull();
  });
});

describe("snapToCandidate", () => {
  const candidates = [
    { candidate_id: "P3:high", point: [95, 0, 12] as [number, number, number] },
    { candidate_id: "P3:mid", point: [95, 0, 10.5] as [number, number, number] },
    { candidate_id: "P3:low", point: [95, 0, 8.5] as [number, number, number] },
  ];

  it("snaps to the nearest candidate inside the radius", () => {
    const c = snapToCandidate([95, 0, 12.4], candidates, 0.6);
    expect(c?.candidate_id).toBe("P3:high");
  });

  it("does not snap outside the radius", () => {
    expect(snapToCandidate([95, 0, 9.7], candidates, 0.6)).toBeNull();
  });
});

describe("catenary helpers", () => {
  it("passes through both attachments", () => {
    // symmetric attachments: u_v = L/2
    const L = 45;
    const a = 800;
    const v_a = 12;
    const u_v = L / 2;
    const v_v = v_a - 2 * a * Math.sinh(L / (4 * a)) ** 2;
    const pts = catenaryWorldPoints(A, B, { u_v, v_v, a }, 9);
    expect(pts[0][2]).toBeCloseTo(12, 6);
    expect(pts[8][2]).toBeCloseTo(12, 6);
    expect(pts[4][2]).toBeCloseTo(v_v, 6);
  });

  it("displacement measures 3D distance", () => {
    expect(displacement([0, 0, 0], [0, 0, 1.5])).toBeCloseTo(1.5);
    expect(displacement([0, 0, 0], [3, 4, 0])).toBeCloseTo(5);
  });
});
