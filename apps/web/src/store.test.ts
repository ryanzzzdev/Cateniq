import { describe, expect, it } from "vitest";
import type { Dataset, Vec3 } from "./api";
import { WorkbenchStore } from "./store";

function fakeDataset(): Dataset {
  return {
    dataset_id: "corridor-a",
    role: "demo",
    schema_version: 1,
    generator: { name: "g", version: 1, seed: 1 },
    coordinate_convention: { units: "m", axes: "rh", up: "+Z" },
    poles: [],
    spans: [{ span_id: "S2", pole_a: "P2", pole_b: "P3" }],
    predictions: {
      S2: {
        attach_a: [50, 0, 12],
        attach_b: [95, 0, 10.5],
        params: { u_v: 0, v_v: 0, a: 900 },
        plane_u: [1, 0],
      },
    },
    observations: {},
    context: null,
  };
}

function readyStore() {
  const s = new WorkbenchStore();
  s.setLoading("corridor-a");
  s.setReady(fakeDataset(), {
    dataset_id: "corridor-a",
    spans: [],
    issue_count: 0,
  });
  return s;
}

describe("workbench store", () => {
  it("draft → commit produces one undoable command", () => {
    const s = readyStore();
    s.beginDraft("S2", "b");
    s.moveDraft([95, 0, 10.9]);
    s.moveDraft([95, 0, 12.0], "P3:high"); // one drag, many moves
    const cmd = s.commitDraft();
    expect(s.get().past).toHaveLength(1);
    expect(cmd!.snappedTo).toBe("P3:high");
    expect(s.attachFor("S2", "b")).toEqual([95, 0, 12]);
  });

  it("cancel discards the draft without an undo entry", () => {
    const s = readyStore();
    s.beginDraft("S2", "b");
    s.moveDraft([95, 0, 12]);
    s.cancelDraft();
    expect(s.get().past).toHaveLength(0);
    expect(s.attachFor("S2", "b")).toEqual([95, 0, 10.5]); // prediction restored
  });

  it("undo/redo round-trips; a new commit clears redo", () => {
    const s = readyStore();
    s.beginDraft("S2", "b");
    s.moveDraft([95, 0, 12], "P3:high");
    s.commitDraft();
    s.undo();
    expect(s.attachFor("S2", "b")).toEqual([95, 0, 10.5]);
    s.redo();
    expect(s.attachFor("S2", "b")).toEqual([95, 0, 12]);
    s.undo();
    s.beginDraft("S2", "b");
    s.moveDraft([95, 0, 9.9]);
    s.commitDraft();
    expect(s.get().future).toHaveLength(0);
    expect(s.attachFor("S2", "b")).toEqual([95, 0, 9.9]);
  });

  it("no-move commit produces no command", () => {
    const s = readyStore();
    s.beginDraft("S2", "b");
    s.commitDraft();
    expect(s.get().past).toHaveLength(0);
  });

  it("selection is blocked while a draft is open", () => {
    const s = readyStore();
    s.select("S2");
    s.beginDraft("S2", "a");
    s.select(null); // must not deselect mid-draft
    expect(s.get().selectedSpanId).toBe("S2");
    s.cancelDraft();
    s.select(null);
    expect(s.get().selectedSpanId).toBeNull();
  });

  function fitFor(a: Vec3, b: Vec3) {
    return {
      fit: {
        status: "ok",
        basis: "corrected",
        rms: 0.03,
        reason: null,
        curve: null,
        issues: [],
        lateralRms: null,
      },
      a,
      b,
    };
  }
  const A: Vec3 = [50, 0, 12];
  const B_PRED: Vec3 = [95, 0, 10.5];
  const B_EDIT: Vec3 = [95, 0, 12];

  it("recorded fits go stale when the span is edited again", () => {
    const s = readyStore();
    const f = fitFor(A, B_PRED);
    s.recordFit("S2", f.fit, s.get().editVersion, f.a, f.b);
    s.beginDraft("S2", "b");
    s.moveDraft(B_EDIT);
    s.commitDraft();
    expect(s.get().lastFit["S2"].stale).toBe(true);
    const f2 = fitFor(A, B_EDIT);
    s.recordFit("S2", f2.fit, s.get().editVersion, f2.a, f2.b);
    expect(s.get().lastFit["S2"].stale).toBe(false);
    s.undo();
    expect(s.get().lastFit["S2"].stale).toBe(true);
  });

  it("draft movement flags an already-recorded fit before commit", () => {
    const s = readyStore();
    const f = fitFor(A, B_PRED);
    s.recordFit("S2", f.fit, s.get().editVersion, f.a, f.b);
    s.beginDraft("S2", "b");
    s.moveDraft(B_EDIT);
    expect(s.get().lastFit["S2"].stale).toBe(true);
  });

  it("cancelling a moved draft invalidates an in-flight result", () => {
    const s = readyStore();
    s.beginDraft("S2", "b");
    s.moveDraft(B_EDIT);
    const requestedAt = s.get().editVersion; // request sent at draft inputs
    s.cancelDraft(); // inputs revert to the prediction
    const f = fitFor(A, B_EDIT);
    s.recordFit("S2", f.fit, requestedAt, f.a, f.b);
    expect(s.get().lastFit["S2"].stale).toBe(true);
  });

  it("cancel restores a recorded fit whose inputs it reverts to", () => {
    const s = readyStore();
    const f = fitFor(A, B_PRED);
    s.recordFit("S2", f.fit, s.get().editVersion, f.a, f.b);
    s.beginDraft("S2", "b");
    s.moveDraft(B_EDIT);
    expect(s.get().lastFit["S2"].stale).toBe(true);
    s.cancelDraft(); // back to the inputs the fit was computed for
    expect(s.get().lastFit["S2"].stale).toBe(false);
  });

  it("a fit response for an older edit version arrives stale", () => {
    const s = readyStore();
    const f = fitFor(A, B_PRED);
    const requestedAt = s.get().editVersion;
    // Edits land while the request is in flight.
    s.beginDraft("S2", "b");
    s.moveDraft(B_EDIT);
    s.commitDraft();
    s.recordFit("S2", f.fit, requestedAt, f.a, f.b);
    expect(s.get().lastFit["S2"].stale).toBe(true);
  });

  it("a late response cannot replace a newer result", () => {
    const s = readyStore();
    const old = fitFor(A, B_PRED);
    const newer = fitFor(A, B_EDIT);
    newer.fit.status = "infeasible";
    newer.fit.rms = 0.8;
    s.recordFit("S2", newer.fit, 5, newer.a, newer.b);
    s.recordFit("S2", old.fit, 3, old.a, old.b);
    expect(s.get().lastFit["S2"].status).toBe("infeasible");
    expect(s.get().lastFit["S2"].version).toBe(5);
  });
});
