import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getProposals, approveAll, type Proposal } from '../api'
import ProposalCard from '../components/ProposalCard'

export default function RunDetail() {
  const { id } = useParams<{ id: string }>()
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [approving, setApproving] = useState(false)
  const [approveResult, setApproveResult] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getProposals(id)
      .then(setProposals)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [id])

  async function handleApproveAll() {
    if (!id) return
    setApproving(true)
    setApproveResult(null)
    try {
      const result = await approveAll(id)
      setApproveResult(`Approved ${result.approved}, failed ${result.failed}`)
      const refreshed = await getProposals(id)
      setProposals(refreshed)
    } catch (e) {
      setApproveResult(String(e))
    } finally {
      setApproving(false)
    }
  }

  const pendingCount = proposals.filter((p) => p.status === 'pending').length

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-blue-600 hover:underline text-sm">
          ← All runs
        </Link>
        <h1 className="text-2xl font-semibold">Run proposals</h1>
        {id && (
          <span className="text-xs font-mono text-gray-400">{id.slice(0, 8)}…</span>
        )}
      </div>

      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && !error && proposals.length === 0 && (
        <p className="text-gray-500">No proposals for this run.</p>
      )}

      {!loading && proposals.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500">
              {proposals.length} proposal{proposals.length !== 1 ? 's' : ''},{' '}
              {pendingCount} pending
            </p>
            {pendingCount > 0 && (
              <button
                className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                disabled={approving}
                onClick={handleApproveAll}
              >
                {approving ? 'Approving…' : 'Approve all'}
              </button>
            )}
          </div>
          {approveResult && (
            <p className="text-sm text-gray-600 mb-4">{approveResult}</p>
          )}
          <div className="space-y-4">
            {proposals.map((p) => (
              <ProposalCard key={p.id} proposal={p} runId={id!} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
