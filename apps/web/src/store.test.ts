import { describe, expect, it } from "vitest";
import type { Dataset } from "./api";
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

  it("recorded fits go stale when the span is edited again", () => {
    const s = readyStore();
    s.recordFit("S2", { status: "ok", rms: 0.03, reason: null, curve: null });
    s.beginDraft("S2", "b");
    s.moveDraft([95, 0, 12]);
    s.commitDraft();
    expect(s.get().lastFit["S2"].stale).toBe(true);
    s.recordFit("S2", { status: "ok", rms: 0.03, reason: null, curve: null });
    expect(s.get().lastFit["S2"].stale).toBe(false);
    s.undo();
    expect(s.get().lastFit["S2"].stale).toBe(true);
  });
});
