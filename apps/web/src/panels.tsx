// Queue and properties panels for the review workbench.

import type { Candidate, Diagnostics, SpanDiagnostics, Vec3 } from "./api";
import { displacement } from "./interaction";
import type { Endpoint, WorkbenchState } from "./store";

export function QueuePanel({
  diagnostics,
  selected,
  onSelect,
}: {
  diagnostics: Diagnostics | null;
  selected: string | null;
  onSelect: (spanId: string) => void;
}) {
  if (!diagnostics) return <aside className="queue" aria-label="diagnostic queue" />;
  const spans = [...diagnostics.spans].sort(
    (x, y) => y.issues.length - x.issues.length,
  );
  return (
    <aside className="queue" aria-label="diagnostic queue">
      <h2>Diagnostics ({diagnostics.issue_count})</h2>
      <ul>
        {spans.map((s) => (
          <QueueRow
            key={s.span_id}
            span={s}
            selected={selected === s.span_id}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </aside>
  );
}

function QueueRow({
  span,
  selected,
  onSelect,
}: {
  span: SpanDiagnostics;
  selected: boolean;
  onSelect: (spanId: string) => void;
}) {
  return (
    <li>
      <button
        className={selected ? "queue-row selected" : "queue-row"}
        aria-pressed={selected}
        onClick={() => onSelect(span.span_id)}
      >
        <span className="queue-id">{span.span_id}</span>
        <span className={`queue-status status-${span.status}`}>
          {span.status}
        </span>
        {span.issues.map((i, n) => (
          <span key={n} className="queue-issue" data-kind={i.kind}>
            {i.kind}: {i.detail}
          </span>
        ))}
        {span.issues.length === 0 && <span className="queue-issue ok">ok</span>}
      </button>
    </li>
  );
}

export function PropertiesPanel({
  state,
  attachFor,
  candidatesFor,
  onBeginDraft,
  onMoveDraft,
  onCommit,
  onCancel,
  onUndo,
  onRedo,
  onValidate,
}: {
  state: WorkbenchState;
  attachFor: (spanId: string, which: Endpoint) => Vec3;
  candidatesFor: (spanId: string, which: Endpoint) => Candidate[];
  onBeginDraft: (spanId: string, which: Endpoint) => void;
  onMoveDraft: (p: Vec3, snappedTo: string | null) => void;
  onCommit: () => void;
  onCancel: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onValidate: (spanId: string) => void;
}) {
  const { dataset, diagnostics, selectedSpanId, draft } = state;
  const diag = diagnostics?.spans.find((s) => s.span_id === selectedSpanId);
  const pred = dataset?.predictions[selectedSpanId ?? ""];
  const span = dataset?.spans.find((s) => s.span_id === selectedSpanId);
  const fit = selectedSpanId ? state.lastFit[selectedSpanId] : null;
  const spanEdits = state.past.filter((e) => e.spanId === selectedSpanId);

  return (
    <aside className="props" aria-label="selected span properties">
      <h2>Span</h2>
      {!selectedSpanId && <p className="muted">No span selected.</p>}
      {selectedSpanId && pred && span && (
        <>
          <dl>
            <dt>id</dt>
            <dd>{selectedSpanId}</dd>
            <dt>status</dt>
            <dd>{diag?.status ?? "?"}</dd>
            <dt>predicted a</dt>
            <dd>{pred.attach_a.map((v) => v.toFixed(2)).join(", ")}</dd>
            <dt>predicted b</dt>
            <dd>{pred.attach_b.map((v) => v.toFixed(2)).join(", ")}</dd>
            {diag?.endpoint_deviations && (
              <>
                <dt>endpoint dev</dt>
                <dd data-testid="endpoint-dev">
                  a {diag.endpoint_deviations[0].toFixed(3)} m, b{" "}
                  {diag.endpoint_deviations[1].toFixed(3)} m
                </dd>
              </>
            )}
            {diag?.rms != null && (
              <>
                <dt>rms</dt>
                <dd>{diag.rms.toFixed(3)} m</dd>
              </>
            )}
          </dl>
          <EndpointEditor
            which="a"
            spanId={selectedSpanId}
            state={state}
            attachFor={attachFor}
            candidates={candidatesFor(selectedSpanId, "a")}
            onBeginDraft={onBeginDraft}
            onMoveDraft={onMoveDraft}
          />
          <EndpointEditor
            which="b"
            spanId={selectedSpanId}
            state={state}
            attachFor={attachFor}
            candidates={candidatesFor(selectedSpanId, "b")}
            onBeginDraft={onBeginDraft}
            onMoveDraft={onMoveDraft}
          />
          {draft && (
            <div className="draft" data-testid="draft-panel">
              <p>
                Draft on endpoint {draft.which}: displacement{" "}
                <strong data-testid="displacement">
                  {displacement(draft.from, draft.current).toFixed(3)} m
                </strong>
                {draft.snappedTo && <> — snapped to {draft.snappedTo}</>}
              </p>
              <div className="row">
                <button onClick={onCommit}>Commit</button>
                <button onClick={onCancel}>Cancel (Esc)</button>
              </div>
            </div>
          )}
          <div className="row">
            <button onClick={onUndo} disabled={!state.past.length || !!draft}>
              Undo
            </button>
            <button onClick={onRedo} disabled={!state.future.length || !!draft}>
              Redo
            </button>
            <button
              onClick={() => onValidate(selectedSpanId)}
              disabled={!spanEdits.length && !draft}
            >
              Validate correction
            </button>
          </div>
          {fit && (
            <p data-testid="fit-result" className={fit.stale ? "fit stale" : "fit"}>
              refit: {fit.status}
              {fit.rms != null && ` (rms ${fit.rms.toFixed(3)} m)`}
              {fit.reason ? ` — ${fit.reason}` : ""}
              {fit.stale ? " — stale (edits since last run)" : ""}
            </p>
          )}
          {spanEdits.length > 0 && (
            <p className="muted" data-testid="unsaved-note">
              {spanEdits.length} local edit(s) — unsaved draft (persistence is
              CAT-009)
            </p>
          )}
        </>
      )}
    </aside>
  );
}

function EndpointEditor({
  which,
  spanId,
  state,
  attachFor,
  candidates,
  onBeginDraft,
  onMoveDraft,
}: {
  which: Endpoint;
  spanId: string;
  state: WorkbenchState;
  attachFor: (spanId: string, which: Endpoint) => Vec3;
  candidates: Candidate[];
  onBeginDraft: (spanId: string, which: Endpoint) => void;
  onMoveDraft: (p: Vec3, snappedTo: string | null) => void;
}) {
  const isActive = state.draft?.spanId === spanId && state.draft.which === which;
  const blocked = !!state.draft && !isActive;
  let shown: Vec3 = attachFor(spanId, which);
  if (isActive) shown = state.draft!.current;

  const setCoord = (i: number, val: string) => {
    const next = [...shown] as Vec3;
    next[i] = Number(val);
    if (isActive) onMoveDraft(next, null);
  };

  return (
    <fieldset className={isActive ? "endpoint active" : "endpoint"}>
      <legend>endpoint {which}</legend>
      {[0, 1, 2].map((i) => (
        <label key={i}>
          {"xyz"[i]}
          <input
            type="number"
            step="0.1"
            data-testid={`coord-${which}-${i}`}
            value={shown[i].toFixed(2)}
            disabled={blocked}
            onFocus={() => {
              if (!isActive && !state.draft) onBeginDraft(spanId, which);
            }}
            onChange={(e) => setCoord(i, e.target.value)}
          />
        </label>
      ))}
      {isActive && (
        <select
          data-testid="candidate-select"
          value={state.draft?.snappedTo ?? ""}
          onChange={(e) => {
            const c = candidates.find(
              (x) => x.candidate_id === e.target.value,
            );
            if (c) onMoveDraft(c.point, c.candidate_id);
          }}
        >
          <option value="">free</option>
          {candidates.map((c) => (
            <option key={c.candidate_id} value={c.candidate_id}>
              snap: {c.candidate_id}
            </option>
          ))}
        </select>
      )}
    </fieldset>
  );
}
