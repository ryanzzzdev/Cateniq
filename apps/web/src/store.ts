// Workbench state: selection, in-progress draft, committed local edits and
// undo/redo. Plain class with subscribers — no store dependency.

import type { Dataset, Diagnostics, Vec3 } from "./api";
import { displacement } from "./interaction";

export type Endpoint = "a" | "b";
export type LoadState = "idle" | "loading" | "ready" | "error";

export interface EditCommand {
  spanId: string;
  which: Endpoint;
  from: Vec3;
  to: Vec3;
  snappedTo: string | null;
}

export interface Draft {
  spanId: string;
  which: Endpoint;
  /** Attachment position when the edit started. */
  from: Vec3;
  current: Vec3;
  snappedTo: string | null;
}

export interface WorkbenchState {
  loadState: LoadState;
  error: string | null;
  datasetId: string | null;
  dataset: Dataset | null;
  diagnostics: Diagnostics | null;
  selectedSpanId: string | null;
  draft: Draft | null;
  /** Committed local edits, in order. Unsaved — persistence is CAT-009. */
  past: EditCommand[];
  /** Redo stack; cleared by any new commit. */
  future: EditCommand[];
  /** Latest constrained-fit preview per span; stale once newer edits land. */
  lastFit: Record<
    string,
    { status: string; rms: number | null; reason: string | null; curve: Vec3[] | null; stale: boolean }
  >;
}

const initial: WorkbenchState = {
  loadState: "idle",
  error: null,
  datasetId: null,
  dataset: null,
  diagnostics: null,
  selectedSpanId: null,
  draft: null,
  past: [],
  future: [],
  lastFit: {},
};

export class WorkbenchStore {
  private state: WorkbenchState = initial;
  private listeners = new Set<() => void>();

  get(): WorkbenchState {
    return this.state;
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private set(patch: Partial<WorkbenchState>) {
    this.state = { ...this.state, ...patch };
    for (const fn of this.listeners) fn();
  }

  setLoading(datasetId: string) {
    this.set({
      ...initial,
      loadState: "loading",
      datasetId,
    });
  }

  setReady(dataset: Dataset, diagnostics: Diagnostics) {
    this.set({ loadState: "ready", dataset, diagnostics, error: null });
  }

  setError(message: string) {
    this.set({ loadState: "error", error: message });
  }

  select(spanId: string | null) {
    if (this.state.draft) return; // cancel or commit the draft first
    this.set({ selectedSpanId: spanId });
  }

  /** Effective endpoint for a span: last committed edit, else the prediction. */
  attachFor(spanId: string, which: Endpoint): Vec3 {
    const pred = this.state.dataset?.predictions[spanId];
    if (!pred) throw new Error(`no prediction for ${spanId}`);
    let current: Vec3 = which === "a" ? pred.attach_a : pred.attach_b;
    for (const e of this.state.past) {
      if (e.spanId === spanId && e.which === which) current = e.to;
    }
    if (
      this.state.draft &&
      this.state.draft.spanId === spanId &&
      this.state.draft.which === which
    ) {
      current = this.state.draft.current;
    }
    return current;
  }

  /** Start a draft on an endpoint (drag or numeric edit). */
  beginDraft(spanId: string, which: Endpoint) {
    const from = this.attachFor(spanId, which);
    this.set({
      selectedSpanId: spanId,
      draft: { spanId, which, from, current: [...from], snappedTo: null },
    });
  }

  moveDraft(to: Vec3, snappedTo: string | null = null) {
    const d = this.state.draft;
    if (!d) return;
    this.set({ draft: { ...d, current: [...to], snappedTo } });
  }

  /** Commit the draft as one logical undoable command. */
  commitDraft(): EditCommand | null {
    const d = this.state.draft;
    if (!d) return null;
    const cmd: EditCommand = {
      spanId: d.spanId,
      which: d.which,
      from: d.from,
      to: d.current,
      snappedTo: d.snappedTo,
    };
    const moved = displacement(d.from, d.current) >= 1e-9;
    const lastFit = { ...this.state.lastFit };
    if (moved && lastFit[d.spanId]) lastFit[d.spanId].stale = true;
    this.set({
      draft: null,
      past: moved ? [...this.state.past, cmd] : this.state.past,
      future: [],
      lastFit,
    });
    return cmd;
  }

  /** Cancel restores the state prior to the draft — nothing was applied. */
  cancelDraft() {
    this.set({ draft: null });
  }

  undo() {
    const past = this.state.past;
    if (!past.length || this.state.draft) return;
    const cmd = past[past.length - 1];
    const lastFit = { ...this.state.lastFit };
    if (lastFit[cmd.spanId]) lastFit[cmd.spanId].stale = true;
    this.set({
      past: past.slice(0, -1),
      future: [cmd, ...this.state.future],
      lastFit,
    });
  }

  redo() {
    const future = this.state.future;
    if (!future.length || this.state.draft) return;
    const [cmd, ...rest] = future;
    const lastFit = { ...this.state.lastFit };
    if (lastFit[cmd.spanId]) lastFit[cmd.spanId].stale = true;
    this.set({ past: [...this.state.past, cmd], future: rest, lastFit });
  }

  recordFit(
    spanId: string,
    fit: { status: string; rms: number | null; reason: string | null; curve: Vec3[] | null },
  ) {
    this.set({
      lastFit: { ...this.state.lastFit, [spanId]: { ...fit, stale: false } },
    });
  }
}
