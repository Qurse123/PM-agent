import { useState } from 'react'
import type { Citation } from '../api'

const CATEGORIES = [
  'wrong_issue',
  'wrong_field',
  'transcript_misread',
  'missing_context',
  'policy',
]

interface Props {
  citations: Citation[]
  onSubmit: (reason: string, category: string, disputedIds: string[]) => void
  onCancel: () => void
}

export default function DenyModal({ citations, onSubmit, onCancel }: Props) {
  const [reason, setReason] = useState('')
  const [category, setCategory] = useState(CATEGORIES[0])
  const [disputed, setDisputed] = useState<Set<string>>(new Set())

  const allSegmentIds = [...new Set(citations.flatMap((c) => c.segment_ids))]

  function toggle(sid: string) {
    setDisputed((prev) => {
      const next = new Set(prev)
      next.has(sid) ? next.delete(sid) : next.add(sid)
      return next
    })
  }

  return (
    <div className="mt-3 border border-red-200 rounded-lg p-4 bg-red-50 space-y-3">
      <p className="font-medium text-sm text-red-800">Deny proposal</p>

      <div>
        <label className="block text-xs text-gray-600 mb-1">Reason</label>
        <textarea
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why is this proposal wrong?"
        />
      </div>

      <div>
        <label className="block text-xs text-gray-600 mb-1">Category</label>
        <select
          className="border border-gray-300 rounded px-2 py-1 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {allSegmentIds.length > 0 && (
        <div>
          <label className="block text-xs text-gray-600 mb-1">Disputed segments</label>
          <div className="space-y-1">
            {allSegmentIds.map((sid) => (
              <label key={sid} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={disputed.has(sid)}
                  onChange={() => toggle(sid)}
                />
                {sid}
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button
          className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
          disabled={!reason.trim()}
          onClick={() => onSubmit(reason.trim(), category, [...disputed])}
        >
          Submit denial
        </button>
        <button
          className="px-3 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
