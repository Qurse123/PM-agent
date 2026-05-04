const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface Run {
  id: string;
  conference_record_id: string;
  title: string | null;
  status: string;
  created_at: string;
  segment_count: number;
  proposal_count: number;
  pending_proposal_count: number;
}

export interface Citation {
  id: string;
  segment_ids: string[];
  quote: string;
  rationale: string;
}

export interface Proposal {
  id: string;
  run_id: string;
  target: string;
  operation: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown>;
  status: string;
  created_at: string;
  citations: Citation[];
}

export interface ApproveAllResult {
  approved: number;
  failed: number;
  results: { proposal_id: string; status: string; error?: string }[];
}

export interface DenyBody {
  reason: string;
  category: string;
  disputed_segment_ids: string[];
}

export interface CreateRunBody {
  title: string;
  transcript_text: string;
}

export function getRuns(): Promise<Run[]> {
  return request<Run[]>("/runs");
}

export function getRun(id: string): Promise<Run> {
  return request<Run>(`/runs/${id}`);
}

export function createRun(body: CreateRunBody): Promise<Run> {
  return request<Run>("/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteRun(id: string): Promise<void> {
  return request<void>(`/runs/${id}`, { method: "DELETE" });
}

export function getProposals(runId: string): Promise<Proposal[]> {
  return request<Proposal[]>(`/runs/${runId}/proposals`);
}

export function approveProposal(runId: string, pid: string): Promise<unknown> {
  return request<unknown>(`/runs/${runId}/proposals/${pid}/approve`, {
    method: "POST",
  });
}

export function denyProposal(
  runId: string,
  pid: string,
  body: DenyBody
): Promise<unknown> {
  return request<unknown>(`/runs/${runId}/proposals/${pid}/deny`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function approveAll(runId: string): Promise<ApproveAllResult> {
  return request<ApproveAllResult>(`/runs/${runId}/proposals/approve-all`, {
    method: "POST",
  });
}

export function analyzeRun(runId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/runs/${runId}/analyze`, {
    method: "POST",
  });
}
