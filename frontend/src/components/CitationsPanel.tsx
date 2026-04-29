import type { Citation } from '../api'

interface Props {
  citations: Citation[]
}

export default function CitationsPanel({ citations }: Props) {
  if (citations.length === 0) return null

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Citations</p>
      {citations.map((c) => (
        <div key={c.id} className="bg-gray-50 border border-gray-200 rounded p-3 text-sm">
          <blockquote className="italic text-gray-700 border-l-2 border-gray-300 pl-2 mb-1">
            "{c.quote}"
          </blockquote>
          <p className="text-gray-600 text-xs">{c.rationale}</p>
          <p className="text-gray-400 text-xs mt-1">
            Segments: {c.segment_ids.join(', ')}
          </p>
        </div>
      ))}
    </div>
  )
}
