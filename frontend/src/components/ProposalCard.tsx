import { useState } from 'react'
import type { Proposal } from '../api'
import { approveProposal, denyProposal } from '../api'
import CitationsPanel from './CitationsPanel'
import DiffViewer from './DiffViewer'
import DenyModal from './DenyModal'

interface Props {
  proposal: Proposal
  runId: string
}

const OP_COLORS: Record<string, string> = {
  create: 'bg-green-100 text-green-800',
  update: 'bg-blue-100 text-blue-800',
  delete: 'bg-red-100 text-red-800',
}

export default function ProposalCard({ proposal, runId }: Props) {
  const [status, setStatus] = useState(proposal.status)
  const [showDeny, setShowDeny] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleApprove() {
    setBusy(true)
    setError(null)
    try {
      await approveProposal(runId, proposal.id)
      setStatus('approved')
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleDeny(reason: string, category: string, disputedIds: string[]) {
    setBusy(true)
    setError(null)
    try {
      await denyProposal(runId, proposal.id, {
        reason,
        category,
        disputed_segment_ids: disputedIds,
      })
      setStatus('denied')
      setShowDeny(false)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const cardBg =
    status === 'approved' || status === 'applied'
      ? 'bg-green-50 border-green-200'
      : status === 'denied' || status === 'failed'
        ? 'bg-red-50 border-red-200'
        : 'bg-white border-gray-200'

  const isPending = status === 'pending'

  return (
    <div className={`border rounded-lg p-4 ${cardBg}`}>
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded ${OP_COLORS[proposal.operation] ?? 'bg-gray-100 text-gray-600'}`}
        >
          {proposal.operation}
        </span>
        <span className="text-sm font-medium text-gray-700">{proposal.target}</span>
        <span className="ml-auto text-xs text-gray-400 capitalize">{status}</span>
      </div>

      <DiffViewer before={proposal.before} after={proposal.after} />
      <CitationsPanel citations={proposal.citations} />

      {error && <p className="text-red-600 text-xs mt-2">{error}</p>}

      {isPending && (
        <div className="flex gap-2 mt-3">
          <button
            className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
            disabled={busy}
            onClick={handleApprove}
          >
            Approve
          </button>
          <button
            className="px-3 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
            disabled={busy}
            onClick={() => setShowDeny((v) => !v)}
          >
            Deny
          </button>
        </div>
      )}

      {showDeny && (
        <DenyModal
          citations={proposal.citations}
          onSubmit={handleDeny}
          onCancel={() => setShowDeny(false)}
        />
      )}
    </div>
  )
}
