import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  fetchDataset,
  fetchDatasets,
  fetchDiagnostics,
  postFit,
  type Dataset,
  type Vec3,
} from "./api";
import { PropertiesPanel, QueuePanel } from "./panels";
import { CorridorScene } from "./scene";
import { WorkbenchStore, type Endpoint } from "./store";

const store = new WorkbenchStore();
// Perf instrumentation for the e2e measurements (not user-visible).
declare global {
  interface Window {
    __cateniq_perf?: { scene?: CorridorScene; readyAt?: number };
  }
}
window.__cateniq_perf = {};

export default function App() {
  const viewportRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<CorridorScene | null>(null);
  const [datasetList, setDatasetList] = useState<
    { dataset_id: string; role: string; point_count: number }[]
  >([]);
  const state = useSyncExternalStore(
    useCallback((cb) => store.subscribe(cb), []),
    () => store.get(),
  );

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const scene = new CorridorScene(el);
    sceneRef.current = scene;
    window.__cateniq_perf!.scene = scene;

    scene.onPick = (r) => {
      if (r.kind === "span" && r.spanId) store.select(r.spanId);
      if (r.kind === "none") store.select(null);
      if (r.kind === "handle" && r.spanId && r.which) {
        store.beginDraft(r.spanId, r.which);
      }
    };
    scene.onDragPoint = (p, snapped) => store.moveDraft(p, snapped);
    scene.onDragEnd = () => store.commitDraft();
    return () => scene.dispose();
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const list = await fetchDatasets();
        setDatasetList(list);
        if (list.length) await openDataset(list[0].dataset_id);
      } catch (e) {
        store.setError(String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push store state into the scene whenever it changes.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !state.dataset) return;
    if (scene.datasetId !== state.dataset.dataset_id) {
      scene.datasetId = state.dataset.dataset_id;
      scene.setData(state.dataset, (sid, w) => store.attachFor(sid, w));
    }
    scene.setSelected(state.selectedSpanId);
    scene.syncHandles((sid, w) => store.attachFor(sid, w));
    scene.setDraft(state.draft);
    for (const [sid, f] of Object.entries(state.lastFit)) {
      scene.showFitCurve(sid, f.curve ?? null);
    }
  }, [state]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "Escape") {
        store.cancelDraft();
        return;
      }
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) store.redo();
        else store.undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        store.redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function openDataset(id: string) {
    const s = store.get();
    if ((s.past.length || s.draft) && s.datasetId && s.datasetId !== id) {
      if (!window.confirm("Unsaved local edits will be discarded. Continue?"))
        return;
    }
    store.setLoading(id);
    try {
      const [ds, diag] = await Promise.all([
        fetchDataset(id),
        fetchDiagnostics(id),
      ]);
      store.setReady(ds, diag);
      window.__cateniq_perf!.readyAt = performance.now();
    } catch (e) {
      store.setError(String(e));
    }
  }

  function candidatesFor(ds: Dataset, spanId: string, which: Endpoint) {
    const span = ds.spans.find((x) => x.span_id === spanId);
    const pole = ds.poles.find(
      (p) => p.pole_id === (which === "a" ? span?.pole_a : span?.pole_b),
    );
    return pole?.attachment_candidates ?? [];
  }

  async function validate(spanId: string) {
    const s0 = store.get();
    const id = s0.datasetId;
    if (!id) return;
    // Capture the inputs this request is computed for; a response that comes
    // back for a different version/dataset must not masquerade as current.
    const version = s0.editVersion;
    const attach_a = store.attachFor(spanId, "a");
    const attach_b = store.attachFor(spanId, "b");
    store.beginFit();
    try {
      const res = await postFit(id, {
        span_id: spanId,
        attach_a,
        attach_b,
      });
      if (store.get().datasetId !== id) {
        store.fitFailed();
        return; // dataset switched mid-flight — the result belongs elsewhere
      }
      if (res.constraints) {
        const same = (a: Vec3, b: number[]) =>
          a.every((v, i) => Math.abs(v - b[i]) < 1e-6);
        if (
          !same(attach_a, res.constraints.attach_a) ||
          !same(attach_b, res.constraints.attach_b)
        ) {
          store.fitFailed();
          store.setError("fit response does not match submitted constraints");
          return;
        }
      }
      store.recordFit(
        spanId,
        {
          status: res.status,
          basis: res.basis,
          rms: res.rms,
          reason: res.reason,
          curve: res.fit?.curve ?? null,
          issues: res.issues,
          lateralRms: res.constraints?.obs_lateral_rms_m ?? null,
        },
        version,
        attach_a,
        attach_b,
      );
    } catch (e) {
      store.fitFailed();
      store.setError(String(e));
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Cateniq</h1>
        <select
          aria-label="dataset"
          value={state.datasetId ?? ""}
          onChange={(e) => void openDataset(e.target.value)}
        >
          {datasetList.map((d) => (
            <option key={d.dataset_id} value={d.dataset_id}>
              {d.dataset_id} ({d.point_count.toLocaleString()} pts)
            </option>
          ))}
        </select>
        <span className="status" data-testid="load-status">
          {state.loadState === "ready" && state.dataset
            ? `${state.datasetId} — ${state.dataset.role}`
            : state.loadState}
        </span>
        {state.error && (
          <span className="error" role="alert">
            {state.error}
          </span>
        )}
      </header>
      <QueuePanel
        diagnostics={state.diagnostics}
        selected={state.selectedSpanId}
        onSelect={(sid) => store.select(sid)}
      />
      <main
        className="viewport"
        ref={viewportRef}
        data-testid="viewport"
        aria-label="3D evidence viewport"
      />
      <PropertiesPanel
        state={state}
        attachFor={(sid, w) => store.attachFor(sid, w)}
        candidatesFor={(sid, w) =>
          state.dataset ? candidatesFor(state.dataset, sid, w) : []
        }
        onBeginDraft={(sid, w) => store.beginDraft(sid, w)}
        onMoveDraft={(p: Vec3, snapped) => store.moveDraft(p, snapped)}
        onCommit={() => store.commitDraft()}
        onCancel={() => store.cancelDraft()}
        onUndo={() => store.undo()}
        onRedo={() => store.redo()}
        onValidate={(sid) => void validate(sid)}
      />
    </div>
  );
}
