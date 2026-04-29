const BASE = 'http://localhost:8000'

export interface Run {
  id: string
  conference_record_id: string
  status: string
  created_at: string
  segment_count: number
}

export interface Citation {
  id: string
  segment_ids: string[]
  quote: string
  rationale: string
}

export interface Proposal {
  id: string
  run_id: string
  target: string
  operation: string
  before: Record<string, unknown> | null
  after: Record<string, unknown>
  status: string
  created_at: string
  citations: Citation[]
}

export interface ApproveAllResult {
  approved: number
  failed: number
  results: { proposal_id: string; status: string; error?: string }[]
}

export interface DenyBody {
  reason: string
  category: string
  disputed_segment_ids: string[]
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const getRuns = () => req<Run[]>('/runs')

export const getProposals = (runId: string) =>
  req<Proposal[]>(`/runs/${runId}/proposals`)

export const approveProposal = (runId: string, pid: string) =>
  req<unknown>(`/runs/${runId}/proposals/${pid}/approve`, { method: 'POST' })

export const denyProposal = (runId: string, pid: string, body: DenyBody) =>
  req<unknown>(`/runs/${runId}/proposals/${pid}/deny`, {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const approveAll = (runId: string) =>
  req<ApproveAllResult>(`/runs/${runId}/proposals/approve-all`, { method: 'POST' })
