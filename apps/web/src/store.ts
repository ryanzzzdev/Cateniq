// Workbench state: selection, in-progress draft, committed local edits and
// undo/redo. Plain class with subscribers — no store dependency.

import type { Accepted, Dataset, Diagnostics, Issue, RunRecord, Vec3 } from "./api";
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

export type SavedEdits = Record<string, { attach_a: Vec3; attach_b: Vec3 }>;

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
  /** Authoritative server revision; edits beyond it are local unsaved. */
  revision: number;
  /** Saved constraint set — the durable baseline under local edits. */
  savedEdits: SavedEdits;
  /** Acceptance recorded for the current revision (null otherwise). */
  accepted: Accepted | null;
  /** A save rejected because another session advanced the revision. */
  conflict: { detail: string; current_revision: number } | null;
  savePending: boolean;
  /** Last save attempt — kept so a retry after an uncertain response
   *  replays the same operation ID for the same payload (idempotent). */
  pendingSave: { operation_id: string; edits: SavedEdits } | null;
  /** Latest validation run record (durable attempt, not a preview). */
  run: RunRecord | null;
  runPending: boolean;
}

export interface FitRecord {
  status: string;
  basis: string;
  rms: number | null;
  reason: string | null;
  curve: Vec3[] | null;
  issues: Issue[];
  /** Lateral observation RMS about the corrected plane (provenance). */
  lateralRms: number | null;
  /** Effective attachments this result was computed for; staleness is
   *  judged against the current effective inputs, not the version alone,
   *  so a result recorded for a cancelled draft stays flagged even after
   *  the inputs revert. */
  attachA: Vec3;
  attachB: Vec3;
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
  revision: 0,
  savedEdits: {},
  accepted: null,
  conflict: null,
  savePending: false,
  pendingSave: null,
  run: null,
  runPending: false,
};

/** Effective endpoint in a given state: last committed edit, else the
 *  prediction; an active draft on that endpoint overrides both. */
function attachForIn(
  state: WorkbenchState,
  spanId: string,
  which: Endpoint,
): Vec3 {
  const pred = state.dataset?.predictions[spanId];
  if (!pred) throw new Error(`no prediction for ${spanId}`);
  let current: Vec3 = which === "a" ? pred.attach_a : pred.attach_b;
  const saved = state.savedEdits[spanId];
  if (saved) current = which === "a" ? saved.attach_a : saved.attach_b;
  for (const e of state.past) {
    if (e.spanId === spanId && e.which === which) current = e.to;
  }
  if (
    state.draft &&
    state.draft.spanId === spanId &&
    state.draft.which === which
  ) {
    current = state.draft.current;
  }
  return current;
}

/** True when the recorded result's inputs differ from the state's. */
function fitIsStale(
  rec: FitRecord,
  spanId: string,
  state: WorkbenchState,
): boolean {
  return (
    displacement(rec.attachA, attachForIn(state, spanId, "a")) >= 1e-9 ||
    displacement(rec.attachB, attachForIn(state, spanId, "b")) >= 1e-9
  );
}

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

  setReady(
    dataset: Dataset,
    diagnostics: Diagnostics,
    review?: { revision: number; savedEdits: WorkbenchState["savedEdits"]; accepted: Accepted | null },
  ) {
    this.set({
      loadState: "ready",
      dataset,
      diagnostics,
      error: null,
      ...(review ?? {}),
    });
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
    return attachForIn(this.state, spanId, which);
  }

  /** Start a draft on an endpoint (drag or numeric edit). */
  beginDraft(spanId: string, which: Endpoint) {
    const from = this.attachFor(spanId, which);
    this.set({
      selectedSpanId: spanId,
      draft: { spanId, which, from, current: [...from], snappedTo: null },
    });
  }

  /** Recompute every recorded fit's stale flag against the effective
   *  inputs in `next`. A result is current exactly when the attachments it
   *  was computed for match what the span has — this stays honest across
   *  drafts, cancels, undo and redo (a revert un-stales). */
  private refreshFitStaleness(next: WorkbenchState) {
    const lastFit = { ...next.lastFit };
    let changed = false;
    for (const [spanId, rec] of Object.entries(lastFit)) {
      const stale = fitIsStale(rec, spanId, next);
      if (stale !== rec.stale) {
        lastFit[spanId] = { ...rec, stale };
        changed = true;
      }
    }
    return changed ? lastFit : next.lastFit;
  }

  moveDraft(to: Vec3, snappedTo: string | null = null) {
    const d = this.state.draft;
    if (!d) return;
    // The effective attachment changed — any in-flight fit request now
    // refers to an older version and its response will be stale; a result
    // already recorded is flagged immediately, not only on commit.
    const next: WorkbenchState = {
      ...this.state,
      draft: { ...d, current: [...to], snappedTo },
      editVersion: this.state.editVersion + 1,
    };
    next.lastFit = this.refreshFitStaleness(next);
    this.set(next);
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
    const next: WorkbenchState = {
      ...this.state,
      draft: null,
      past: moved ? [...this.state.past, cmd] : this.state.past,
      future: [],
      editVersion: moved
        ? this.state.editVersion + 1
        : this.state.editVersion,
    };
    next.lastFit = this.refreshFitStaleness(next);
    this.set(next);
    return cmd;
  }

  /** Cancel restores the state prior to the draft — nothing was applied.
   *  If the draft had moved, the effective inputs changed during it, so the
   *  version advances: a late response computed for draft geometry arrives
   *  flagged stale instead of masquerading as current. */
  cancelDraft() {
    const d = this.state.draft;
    if (!d) return;
    const moved = displacement(d.from, d.current) >= 1e-9;
    const next: WorkbenchState = {
      ...this.state,
      draft: null,
      editVersion: moved ? this.state.editVersion + 1 : this.state.editVersion,
    };
    next.lastFit = this.refreshFitStaleness(next);
    this.set(next);
  }

  undo() {
    const past = this.state.past;
    if (!past.length || this.state.draft) return;
    const cmd = past[past.length - 1];
    const next: WorkbenchState = {
      ...this.state,
      past: past.slice(0, -1),
      future: [cmd, ...this.state.future],
      editVersion: this.state.editVersion + 1,
    };
    next.lastFit = this.refreshFitStaleness(next);
    this.set(next);
  }

  redo() {
    const future = this.state.future;
    if (!future.length || this.state.draft) return;
    const [cmd, ...rest] = future;
    const next: WorkbenchState = {
      ...this.state,
      past: [...this.state.past, cmd],
      future: rest,
      editVersion: this.state.editVersion + 1,
    };
    next.lastFit = this.refreshFitStaleness(next);
    this.set(next);
  }

  /** Mark a constrained-fit request as in flight. */
  beginFit() {
    this.set({ fitPending: true });
  }

  /** The in-flight request ended without a recorded result (error/discard). */
  fitFailed() {
    this.set({ fitPending: false });
  }

  /** Record a fit response computed for `version` and the effective
   *  attachments that were submitted. A response arriving after a newer
   *  result never replaces it; a response whose inputs no longer match the
   *  current effective inputs is kept but honestly flagged stale. */
  recordFit(
    spanId: string,
    fit: {
      status: string;
      basis: string;
      rms: number | null;
      reason: string | null;
      curve: Vec3[] | null;
      issues: Issue[];
      lateralRms: number | null;
    },
    version: number,
    attachA: Vec3,
    attachB: Vec3,
  ) {
    const existing = this.state.lastFit[spanId];
    if (existing && existing.version > version) {
      this.set({ fitPending: false });
      return;
    }
    const rec: FitRecord = {
      ...fit,
      attachA,
      attachB,
      version,
      stale: false,
    };
    rec.stale = fitIsStale(rec, spanId, this.state);
    this.set({
      fitPending: false,
      lastFit: { ...this.state.lastFit, [spanId]: rec },
    });
  }

  /** Mark a save request in flight, retaining the submitted operation
   *  so a retry after an uncertain response can replay it. */
  beginSave(op: { operation_id: string; edits: SavedEdits }) {
    this.set({ savePending: true, conflict: null, pendingSave: op });
  }

  /** A save failed without reaching or committing on the server —
   *  the operation stays pending so retry replays the same ID. */
  saveFailed() {
    this.set({ savePending: false });
  }

  /** A save was rejected for a stale base — local edits stay untouched so
   *  the losing session's work remains inspectable. */
  setConflict(detail: string, current_revision: number) {
    this.set({
      savePending: false,
      conflict: { detail, current_revision },
    });
  }

  /** Authoritative review state applied after a save: the saved
   *  constraint set becomes the durable baseline and the acknowledged
   *  edits leave `past`. Local intent that diverged while the save was
   *  in flight — mid-flight commits, undo-to-empty, branch-after-undo —
   *  is rebased onto the new baseline as still-unsaved edits rather than
   *  silently discarded. */
  recordSaved(
    revision: number,
    savedEdits: SavedEdits,
    accepted: Accepted | null,
    acked: EditCommand[],
  ) {
    const pre = this.state;
    // The user's current effective value at every endpoint that could
    // differ from the incoming baseline: local history plus the
    // acknowledged set. (An undone-then-branched endpoint lives in
    // neither history — the acked set still catches it.)
    const touched = new Map<string, Vec3>();
    for (const c of [...pre.past, ...pre.future, ...acked]) {
      const k = `${c.spanId}|${c.which}`;
      if (!touched.has(k)) touched.set(k, attachForIn(pre, c.spanId, c.which));
    }
    const next: WorkbenchState = {
      ...pre,
      savePending: false,
      conflict: null,
      pendingSave: null,
      revision,
      savedEdits,
      accepted,
      past: [],
      future: [],
      editVersion: pre.editVersion + 1,
    };
    // Rebase: keep only commands whose effect still differs from what
    // lies beneath them (acknowledged and redundant commands drop out),
    // then re-express any touched endpoint the baseline doesn't already
    // reproduce — an undone save survives as an explicit local edit.
    const preserved: EditCommand[] = [];
    for (const c of pre.past) {
      if (acked.includes(c)) continue;
      const under = attachForIn({ ...next, past: preserved }, c.spanId, c.which);
      if (displacement(c.to, under) >= 1e-9) preserved.push(c);
    }
    for (const [k, val] of touched) {
      const [spanId, which] = k.split("|") as [string, Endpoint];
      const under = attachForIn({ ...next, past: preserved }, spanId, which);
      if (displacement(val, under) >= 1e-9) {
        preserved.push({ spanId, which, from: under, to: val, snappedTo: null });
      }
    }
    next.past = preserved;
    next.lastFit = this.refreshFitStaleness(next);
    this.set(next);
  }

  /** Mark a validation run request in flight. */
  beginRun() {
    this.set({ runPending: true });
  }

  /** Record a polled/returned run attempt. */
  recordRun(run: RunRecord | null) {
    this.set({ runPending: false, run });
  }

  /** Update acceptance state (after accept or on review refresh). */
  recordAccepted(accepted: Accepted | null) {
    this.set({ accepted });
  }
}
