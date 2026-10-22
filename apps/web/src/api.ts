export type Vec3 = [number, number, number];
export type Vec2 = [number, number];

export interface Candidate {
  candidate_id: string;
  point: Vec3;
}

export interface Pole {
  pole_id: string;
  position: Vec3;
  attachment_candidates: Candidate[];
}

export interface SpanRec {
  span_id: string;
  pole_a: string;
  pole_b: string;
}

export interface PredSpan {
  attach_a: Vec3;
  attach_b: Vec3;
  params: { u_v: number; v_v: number; a: number };
  plane_u: Vec2;
}

export interface PointColumns {
  point_id: number[];
  x: number[];
  y: number[];
  z: number[];
  label: number[];
}

export interface Dataset {
  dataset_id: string;
  role: string;
  schema_version: number;
  generator: { name: string; version: number; seed: number };
  coordinate_convention: { units: string; axes: string; up: string };
  poles: Pole[];
  spans: SpanRec[];
  predictions: Record<string, PredSpan>;
  observations: Record<string, PointColumns>;
  context: PointColumns | null;
}

export interface Issue {
  kind: string;
  detail: string;
  threshold: string;
}

export interface SpanDiagnostics {
  span_id: string;
  status: string;
  /** "prediction" (free fit) or "corrected" (constrained refit). */
  basis: string;
  units: string;
  rms: number | null;
  p95: number | null;
  condition: number | null;
  endpoint_deviations: [number, number] | null;
  issues: Issue[];
}

export interface Diagnostics {
  dataset_id: string;
  spans: SpanDiagnostics[];
  issue_count: number;
}

export interface FitResult {
  span_id: string;
  status: string;
  basis: string;
  units: string;
  rms: number | null;
  p95: number | null;
  reason: string | null;
  fit: { u_v: number; v_v: number; a: number; curve: Vec3[] } | null;
  /** Validation issues from the frozen quality gates (solver status is
   *  separate: a converged fit can still fail validation). */
  issues: Issue[];
  /** Echo of the constraints the refit ran against, plus measured provenance. */
  constraints: {
    attach_a: Vec3;
    attach_b: Vec3;
    off_plane_m: [number, number];
    obs_lateral_rms_m: number;
  } | null;
}

export interface RefitResult {
  dataset_id: string;
  spans: (SpanDiagnostics | FitResult)[];
  issue_count: number;
}

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(`health failed: ${res.status}`);
  return res.json();
}

export async function fetchDatasets(): Promise<
  { dataset_id: string; role: string; span_count: number; point_count: number }[]
> {
  const res = await fetch("/api/datasets");
  if (!res.ok) throw new Error(`datasets failed: ${res.status}`);
  return res.json();
}

export async function fetchDataset(id: string): Promise<Dataset> {
  const res = await fetch(`/api/datasets/${id}`);
  if (!res.ok) throw new Error(`dataset ${id} failed: ${res.status}`);
  return res.json();
}

export async function fetchDiagnostics(id: string): Promise<Diagnostics> {
  const res = await fetch(`/api/datasets/${id}/diagnostics`);
  if (!res.ok) throw new Error(`diagnostics ${id} failed: ${res.status}`);
  return res.json();
}

export async function postFit(
  datasetId: string,
  body: { span_id: string; attach_a: Vec3; attach_b: Vec3 },
): Promise<FitResult> {
  const res = await fetch(`/api/datasets/${datasetId}/fit`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`fit failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function postRefit(
  datasetId: string,
  edits: Record<string, { attach_a: Vec3; attach_b: Vec3 }>,
): Promise<RefitResult> {
  const res = await fetch(`/api/datasets/${datasetId}/refit`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ edits }),
  });
  if (!res.ok)
    throw new Error(`refit failed: ${res.status} ${await res.text()}`);
  return res.json();
}
