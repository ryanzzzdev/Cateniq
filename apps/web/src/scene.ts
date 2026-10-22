// Three.js corridor viewport behind a small adapter: the app calls setData/
// setSelected/setDraft and receives pick/drag callbacks. Direct three.js,
// no rendering abstraction beyond this file.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Dataset, PointColumns, Vec3 } from "./api";
import {
  catenaryWorldPoints,
  rayPlanePoint,
  snapToCandidate,
  spanPlane,
} from "./interaction";
import type { Draft } from "./store";

const LABEL_CONDUCTOR = 1;
const SNAP_RADIUS_M = 0.6;
const SPAN_COLORS = [0x1f9e89, 0x440154, 0x3b528b, 0x21918c, 0xfde725, 0x5ec962];
const HANDLE_COLORS = { a: 0xff9f1c, b: 0xb388eb };

export interface PickResult {
  kind: "handle" | "span" | "none";
  spanId?: string;
  which?: "a" | "b";
}

interface SpanObjects {
  points: THREE.Points;
  curve: THREE.Line;
  draftCurve: THREE.Line;
  handleA: THREE.Mesh;
  handleB: THREE.Mesh;
  mid: Vec3;
}

function columnsToPositions(c: PointColumns): Float32Array {
  const n = c.x.length;
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    out[i * 3] = c.x[i];
    out[i * 3 + 1] = c.y[i];
    out[i * 3 + 2] = c.z[i];
  }
  return out;
}

function conductorOnly(c: PointColumns): PointColumns {
  const idx = c.label.map((l, i) => (l === LABEL_CONDUCTOR ? i : -1));
  const keep = idx.filter((i) => i >= 0);
  return {
    point_id: keep.map((i) => c.point_id[i]),
    x: keep.map((i) => c.x[i]),
    y: keep.map((i) => c.y[i]),
    z: keep.map((i) => c.z[i]),
    label: keep.map(() => LABEL_CONDUCTOR),
  };
}

export class CorridorScene {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private raycaster = new THREE.Raycaster();
  private spans = new Map<string, SpanObjects>();
  private contextPoints: THREE.Points | null = null;
  private candidateMeshes: THREE.Mesh[] = [];
  private ghostHandle: THREE.Mesh;
  private dispLine: THREE.Line;
  private snapMarker: THREE.Mesh;
  private spanObjects: SpanObjects | null = null;
  private dataset: Dataset | null = null;
  datasetId: string | null = null;
  private rafId = 0;
  private frameTimes: number[] = [];
  private lastFrame = 0;

  onPick: (r: PickResult) => void = () => {};
  onDragPoint: (p: Vec3, snappedId: string | null) => void = () => {};
  onDragEnd: () => void = () => {};
  /** Plane for the in-progress drag (set while a handle is held). */
  private dragPlane: ReturnType<typeof spanPlane> | null = null;
  private dragCandidates: { candidate_id: string; point: Vec3 }[] = [];

  constructor(private container: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 2000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(100, -140, 90);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(100, 0, 10);

    this.scene.background = new THREE.Color(0x14181d);
    this.scene.add(new THREE.AxesHelper(10));
    const grid = new THREE.GridHelper(400, 40, 0x2a3b45, 0x22303a);
    grid.rotation.x = Math.PI / 2; // z-up ground plane
    this.scene.add(grid);

    this.ghostHandle = new THREE.Mesh(
      new THREE.SphereGeometry(0.35, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0x4dd0e1 }),
    );
    this.ghostHandle.visible = false;
    this.scene.add(this.ghostHandle);
    this.dispLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0x4dd0e1 }),
    );
    this.dispLine.visible = false;
    this.scene.add(this.dispLine);
    this.snapMarker = new THREE.Mesh(
      new THREE.TorusGeometry(0.5, 0.08, 8, 24),
      new THREE.MeshBasicMaterial({ color: 0x4dd0e1 }),
    );
    this.snapMarker.visible = false;
    this.scene.add(this.snapMarker);

    this.resize();
    new ResizeObserver(() => this.resize()).observe(container);
    this.renderer.domElement.addEventListener("pointerdown", (e) =>
      this.pointerDown(e),
    );
    this.renderer.domElement.addEventListener("pointermove", (e) =>
      this.pointerMove(e),
    );
    this.renderer.domElement.addEventListener("pointerup", () =>
      this.pointerUp(),
    );
    this.renderLoop();
  }

  private resize() {
    const w = this.container.clientWidth || 1;
    const h = this.container.clientHeight || 1;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private renderLoop() {
    const step = (t: number) => {
      if (this.lastFrame) this.frameTimes.push(t - this.lastFrame);
      if (this.frameTimes.length > 600) this.frameTimes.shift();
      this.lastFrame = t;
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      this.rafId = requestAnimationFrame(step);
    };
    this.rafId = requestAnimationFrame(step);
  }

  /** Total rendered point count (for tests/measurement). */
  countPoints(): number {
    let n = 0;
    for (const s of this.spans.values()) {
      n += s.points.geometry.getAttribute("position").count;
    }
    if (this.contextPoints) {
      n += this.contextPoints.geometry.getAttribute("position").count;
    }
    return n;
  }

  /** Recent inter-frame deltas (ms), for performance measurement. */
  frameStats(): { count: number; p50: number; p95: number; max: number } {
    const t = [...this.frameTimes].sort((a, b) => a - b);
    const pick = (q: number) => t[Math.min(t.length - 1, Math.floor(q * t.length))] ?? 0;
    return { count: t.length, p50: pick(0.5), p95: pick(0.95), max: t[t.length - 1] ?? 0 };
  }

  private pointerRay(e: PointerEvent): { origin: Vec3; dir: Vec3 } {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    const r = this.raycaster.ray;
    return {
      origin: [r.origin.x, r.origin.y, r.origin.z],
      dir: [r.direction.x, r.direction.y, r.direction.z],
    };
  }

  private pickables(): THREE.Object3D[] {
    const objs: THREE.Object3D[] = [];
    for (const s of this.spans.values()) {
      objs.push(s.handleA, s.handleB, s.curve, s.points);
    }
    return objs;
  }

  private pointerDown(e: PointerEvent) {
    if (e.button !== 0 || this.dragPlane) return;
    this.pointerRay(e); // positions the raycaster from the pointer
    this.raycaster.params.Points = { threshold: 0.35 };
    const hits = this.raycaster.intersectObjects(this.pickables(), false);
    const hit = hits.find((h) => h.object.visible)?.object;
    if (hit instanceof THREE.Mesh && hit.userData.type === "handle") {
      const { spanId, which } = hit.userData;
      this.beginDrag(spanId, which, e);
      return;
    }
    if (hit && hit.userData.spanId) {
      this.onPick({ kind: "span", spanId: hit.userData.spanId });
    } else {
      this.onPick({ kind: "none" });
    }
  }

  private beginDrag(spanId: string, which: "a" | "b", e: PointerEvent) {
    if (!this.dataset) return;
    void this.dataset.predictions[spanId];
    const a = this.effectiveAttach(spanId, "a");
    const b = this.effectiveAttach(spanId, "b");
    this.dragPlane = spanPlane(a, b);
    const span = this.dataset.spans.find((s) => s.span_id === spanId);
    const pole = this.dataset.poles.find(
      (p) => p.pole_id === (which === "a" ? span?.pole_a : span?.pole_b),
    );
    this.dragCandidates = pole?.attachment_candidates ?? [];
    this.controls.enabled = false;
    this.renderer.domElement.setPointerCapture(e.pointerId);
    this.onPick({ kind: "handle", spanId, which });
  }

  private pointerMove(e: PointerEvent) {
    if (!this.dragPlane) return;
    const { origin, dir } = this.pointerRay(e);
    const p = rayPlanePoint(origin, dir, this.dragPlane);
    if (!p) return;
    const snap = snapToCandidate(p, this.dragCandidates, SNAP_RADIUS_M);
    this.onDragPoint(snap ? snap.point : p, snap ? snap.candidate_id : null);
  }

  private pointerUp() {
    if (!this.dragPlane) return;
    this.dragPlane = null;
    this.dragCandidates = [];
    this.controls.enabled = true;
    this.onDragEnd();
  }

  private effectiveAttach(spanId: string, which: "a" | "b"): Vec3 {
    const obj = this.spans.get(spanId);
    const h = which === "a" ? obj?.handleA : obj?.handleB;
    return h ? [h.position.x, h.position.y, h.position.z] : [0, 0, 0];
  }

  /** Build all objects for a dataset; positions come from attachGetter so
   *  committed edits are reflected without rebuilding. */
  setData(ds: Dataset, attachGetter: (spanId: string, which: "a" | "b") => Vec3) {
    this.clearData();
    this.dataset = ds;
    ds.spans.forEach((span, i) => {
      const color = SPAN_COLORS[i % SPAN_COLORS.length];
      const obs = ds.observations[span.span_id];
      const ptsGeo = new THREE.BufferGeometry();
      ptsGeo.setAttribute(
        "position",
        new THREE.BufferAttribute(columnsToPositions(conductorOnly(obs)), 3),
      );
      const points = new THREE.Points(
        ptsGeo,
        new THREE.PointsMaterial({ color, size: 0.22 }),
      );
      points.userData.spanId = span.span_id;
      this.scene.add(points);

      const pred = ds.predictions[span.span_id];
      const curveGeo = new THREE.BufferGeometry().setFromPoints(
        catenaryWorldPoints(pred.attach_a, pred.attach_b, pred.params).map(
          (p) => new THREE.Vector3(...p),
        ),
      );
      const curve = new THREE.Line(
        curveGeo,
        new THREE.LineBasicMaterial({ color: 0xb0bec5 }),
      );
      curve.userData.spanId = span.span_id;
      this.scene.add(curve);

      const draftCurve = new THREE.Line(
        new THREE.BufferGeometry(),
        new THREE.LineDashedMaterial({ color: 0x4dd0e1, dashSize: 0.6, gapSize: 0.4 }),
      );
      draftCurve.visible = false;
      this.scene.add(draftCurve);

      const mkHandle = (which: "a" | "b") => {
        const m = new THREE.Mesh(
          new THREE.SphereGeometry(0.45, 20, 20),
          new THREE.MeshBasicMaterial({ color: HANDLE_COLORS[which] }),
        );
        m.userData = { type: "handle", spanId: span.span_id, which };
        m.position.set(...attachGetter(span.span_id, which));
        this.scene.add(m);
        return m;
      };
      const handleA = mkHandle("a");
      const handleB = mkHandle("b");
      const mid: Vec3 = [
        (pred.attach_a[0] + pred.attach_b[0]) / 2,
        (pred.attach_a[1] + pred.attach_b[1]) / 2,
        (pred.attach_a[2] + pred.attach_b[2]) / 2,
      ];
      this.spans.set(span.span_id, {
        points,
        curve,
        draftCurve,
        handleA,
        handleB,
        mid,
      });
    });

    if (ds.context) {
      const g = new THREE.BufferGeometry();
      g.setAttribute(
        "position",
        new THREE.BufferAttribute(columnsToPositions(ds.context), 3),
      );
      this.contextPoints = new THREE.Points(
        g,
        new THREE.PointsMaterial({ color: 0x546e7a, size: 0.18 }),
      );
      this.scene.add(this.contextPoints);
    }

    for (const pole of ds.poles) {
      for (const c of pole.attachment_candidates) {
        const m = new THREE.Mesh(
          new THREE.SphereGeometry(0.18, 12, 12),
          new THREE.MeshBasicMaterial({ color: 0x37474f }),
        );
        m.position.set(...c.point);
        m.userData.candidateId = c.candidate_id;
        this.candidateMeshes.push(m);
        this.scene.add(m);
      }
      const post = new THREE.Mesh(
        new THREE.CylinderGeometry(0.25, 0.3, 1, 8),
        new THREE.MeshBasicMaterial({ color: 0x455a64 }),
      );
      const maxZ = Math.max(...pole.attachment_candidates.map((c) => c.point[2]));
      post.scale.y = maxZ;
      post.position.set(pole.position[0], pole.position[1], maxZ / 2);
      this.scene.add(post);
      this.candidateMeshes.push(post);
    }
  }

  private clearData() {
    for (const s of this.spans.values()) {
      this.scene.remove(s.points, s.curve, s.draftCurve, s.handleA, s.handleB);
    }
    this.spans.clear();
    if (this.contextPoints) this.scene.remove(this.contextPoints);
    this.contextPoints = null;
    for (const m of this.candidateMeshes) this.scene.remove(m);
    this.candidateMeshes = [];
  }

  setSelected(spanId: string | null) {
    for (const [id, s] of this.spans) {
      const sel = id === spanId;
      (s.curve.material as THREE.LineBasicMaterial).color.setHex(
        sel ? 0x4dd0e1 : 0xb0bec5,
      );
      (s.points.material as THREE.PointsMaterial).size = sel ? 0.3 : 0.22;
      s.handleA.visible = sel;
      s.handleB.visible = sel;
    }
    if (spanId && this.spans.has(spanId)) {
      this.spanObjects = this.spans.get(spanId)!;
      this.controls.target.set(...this.spanObjects.mid);
    }
  }

  /** Show the in-progress draft: moved handle ghost, displacement, snap ring. */
  setDraft(draft: Draft | null) {
    this.ghostHandle.visible = !!draft;
    this.dispLine.visible = !!draft;
    this.snapMarker.visible = !!draft?.snappedTo;
    if (!draft) return;
    this.ghostHandle.position.set(...draft.current);
    this.dispLine.geometry.setFromPoints([
      new THREE.Vector3(...draft.from),
      new THREE.Vector3(...draft.current),
    ]);
    if (draft.snappedTo) {
      const c = this.candidateMeshes.find(
        (m) => m.userData.candidateId === draft.snappedTo,
      );
      if (c) {
        this.snapMarker.position.copy(c.position);
        this.snapMarker.lookAt(this.camera.position);
      }
    }
  }

  /** Show/hide the dashed refit preview curve for a span. */
  showFitCurve(spanId: string, curve: Vec3[] | null) {
    const s = this.spans.get(spanId);
    if (!s) return;
    s.draftCurve.visible = !!curve;
    if (curve) {
      s.draftCurve.geometry.setFromPoints(
        curve.map((p) => new THREE.Vector3(...p)),
      );
      s.draftCurve.computeLineDistances();
    }
  }

  /** Project a world point to page pixel coordinates (for tests). */
  worldToScreen(p: Vec3): { x: number; y: number } {
    const v = new THREE.Vector3(...p).project(this.camera);
    const rect = this.renderer.domElement.getBoundingClientRect();
    return {
      x: rect.left + ((v.x + 1) / 2) * rect.width,
      y: rect.top + ((1 - v.y) / 2) * rect.height,
    };
  }

  /** After commit/undo/redo: sync handle positions to effective attachments. */
  syncHandles(attachGetter: (spanId: string, which: "a" | "b") => Vec3) {
    for (const [id, s] of this.spans) {
      s.handleA.position.set(...attachGetter(id, "a"));
      s.handleB.position.set(...attachGetter(id, "b"));
    }
  }

  dispose() {
    cancelAnimationFrame(this.rafId);
    this.clearData();
    this.controls.dispose();
    this.renderer.dispose();
  }
}
