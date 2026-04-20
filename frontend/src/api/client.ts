const BASE = import.meta.env.VITE_API_BASE || "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    let detail: string;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      detail = await res.text();
    }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return (await res.json()) as T;
}

async function reqBlob(path: string, init?: RequestInit): Promise<Blob> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.blob();
}

export interface PipelineResult {
  ok: boolean;
  original_filename: string;
  stored_as: string;
  size_bytes: number;
  counts: Record<string, number>;
  logs: string[];
}

export async function buildPipeline(file: File): Promise<PipelineResult> {
  const form = new FormData();
  form.append("file", file);
  return req("/api/pipeline/build", { method: "POST", body: form });
}

export async function pipelineStatus(): Promise<{ db_exists: boolean; db_size_bytes: number }> {
  return req("/api/pipeline/status");
}

export interface TargetsResponse {
  mode: string;
  source: string;
  grouped_available: boolean;
  targets: string[];
}

export async function getTargets(mode: "host" | "zone", source: "exploded" | "grouped"): Promise<TargetsResponse> {
  return req(`/api/targets?mode=${mode}&source=${source}`);
}

export interface Row {
  [key: string]: unknown;
  row_tag?: string | null;
}

export interface AnalyzeResponse {
  mode: "host" | "zone";
  columns: string[];
  rows: Row[];
}

export async function analyze(payload: {
  target: string;
  target_is_zone: boolean;
  view_by_zones: boolean;
  data_source: "exploded" | "grouped";
}): Promise<AnalyzeResponse> {
  return req("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface Annotation {
  policy_name: string;
  classification: string | null;
  notes: string | null;
  updated_at: string | null;
}

export async function getAnnotation(policyName: string): Promise<Annotation> {
  return req(`/api/annotations/${encodeURIComponent(policyName)}`);
}

export async function putAnnotation(
  policyName: string,
  payload: { classification: string | null; notes: string | null },
): Promise<{ ok: boolean }> {
  return req(`/api/annotations/${encodeURIComponent(policyName)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteAnnotation(policyName: string): Promise<{ ok: boolean }> {
  return req(`/api/annotations/${encodeURIComponent(policyName)}`, {
    method: "DELETE",
  });
}

export interface Category {
  name: string;
  color: string;
}

export async function getCategories(): Promise<{ categories: Category[] }> {
  return req("/api/settings/categories");
}

export async function putCategories(categories: Category[]): Promise<{ categories: Category[] }> {
  return req("/api/settings/categories", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categories }),
  });
}

export async function exportMermaid(payload: {
  rows: Row[];
  target: string;
  target_is_zone: boolean;
  view_by_zones: boolean;
  fenced: boolean;
}): Promise<Blob> {
  return reqBlob("/api/export/mermaid", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function exportTableFormat(
  format: "csv" | "yaml" | "excel",
  payload: {
    headers: string[];
    rows: (string | number)[][];
    target: string;
    view_by_zones: boolean;
    full_policies?: boolean;
  },
): Promise<Blob> {
  return reqBlob(`/api/export/${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function downloadBlob(blob: Blob, suggestedName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
