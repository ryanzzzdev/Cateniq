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
  /** Bumped whenever effective attachments change (draft move, commit,
   *  undo/redo). Fit requests capture it; responses for older versions are
   *  stale and can never replace a result recorded for a newer version. */
  editVersion: number;
  /** Latest constrained-fit preview per span. */
  lastFit: Record<string, FitRecord>;
  /** A constrained-fit request is in flight. */
  fitPending: boolean;
}

export interface FitRecord {
  status: string;
  basis: string;
  rms: number | null;
  reason: string | null;
  curve: Vec3[] | null;
  /** editVersion this result was computed for. */
  version: number;
  stale: boolean;
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
  editVersion: 0,
  lastFit: {},
  fitPending: false,
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
    // The effective attachment changed — any in-flight fit request now
    // refers to an older version and its response will be stale.
    this.set({
      draft: { ...d, current: [...to], snappedTo },
      editVersion: this.state.editVersion + 1,
    });
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
      editVersion: moved
        ? this.state.editVersion + 1
        : this.state.editVersion,
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
      editVersion: this.state.editVersion + 1,
    });
  }

  redo() {
    const future = this.state.future;
    if (!future.length || this.state.draft) return;
    const [cmd, ...rest] = future;
    const lastFit = { ...this.state.lastFit };
    if (lastFit[cmd.spanId]) lastFit[cmd.spanId].stale = true;
    this.set({
      past: [...this.state.past, cmd],
      future: rest,
      lastFit,
      editVersion: this.state.editVersion + 1,
    });
  }

  /** Mark a constrained-fit request as in flight. */
  beginFit() {
    this.set({ fitPending: true });
  }

  /** The in-flight request ended without a recorded result (error/discard). */
  fitFailed() {
    this.set({ fitPending: false });
  }

  /** Record a fit response computed for `version`. A response arriving after
   *  a newer result never replaces it; a response for an older edit version
   *  is kept but honestly flagged stale. */
  recordFit(
    spanId: string,
    fit: {
      status: string;
      basis: string;
      rms: number | null;
      reason: string | null;
      curve: Vec3[] | null;
    },
    version: number,
  ) {
    const existing = this.state.lastFit[spanId];
    if (existing && existing.version > version) {
      this.set({ fitPending: false });
      return;
    }
    this.set({
      fitPending: false,
      lastFit: {
        ...this.state.lastFit,
        [spanId]: { ...fit, version, stale: version !== this.state.editVersion },
      },
    });
  }
}
