import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getRuns, type Run } from '../api'

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  analyzing: 'bg-blue-100 text-blue-800',
  ready: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

export default function RunsList() {
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getRuns()
      .then(setRuns)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold mb-6">Runs</h1>

      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && !error && runs.length === 0 && (
        <p className="text-gray-500">No runs yet.</p>
      )}

      {runs.length > 0 && (
        <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
          <thead className="bg-gray-50 text-left text-gray-600 uppercase text-xs">
            <tr>
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Segments</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-gray-500">
                  {run.id.slice(0, 8)}…
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[run.status] ?? 'bg-gray-100 text-gray-600'}`}
                  >
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-3">{run.segment_count}</td>
                <td className="px-4 py-3 text-gray-500">
                  {new Date(run.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    to={`/runs/${run.id}`}
                    className="text-blue-600 hover:underline font-medium"
                  >
                    Review →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
