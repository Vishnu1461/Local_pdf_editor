import type { DetectionResult, DocumentInfo, Field, SaveReport, TemplateSummary } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep the status text */
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export async function uploadDocument(file: File): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentInfo>("/api/documents", { method: "POST", body: form });
}

export async function detectFields(docId: string): Promise<DetectionResult> {
  return request<DetectionResult>(`/api/documents/${docId}/detect`, { method: "POST" });
}

export async function applyTemplate(docId: string, templateId: string): Promise<Field[]> {
  return request<Field[]>(`/api/documents/${docId}/apply-template/${encodeURIComponent(templateId)}`, {
    method: "POST",
  });
}

export async function listTemplates(): Promise<TemplateSummary[]> {
  return request<TemplateSummary[]>("/api/templates");
}

export async function saveDocument(
  docId: string,
  fields: Field[],
  options: { flatten: boolean; fileName: string },
): Promise<SaveReport> {
  return request<SaveReport>(`/api/documents/${docId}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields, flatten: options.flatten, fileName: options.fileName }),
  });
}

export async function downloadOutput(report: SaveReport): Promise<Blob> {
  const res = await fetch(`${API_BASE}${report.downloadUrl}`);
  if (!res.ok) throw new Error(`download failed: ${res.status}`);
  return res.blob();
}

export async function reopenOutput(docId: string, outputId: string): Promise<DocumentInfo> {
  return request<DocumentInfo>(`/api/documents/${docId}/outputs/${outputId}/reopen`, { method: "POST" });
}

export function sourceUrl(docId: string): string {
  return `${API_BASE}/api/documents/${docId}/file`;
}
