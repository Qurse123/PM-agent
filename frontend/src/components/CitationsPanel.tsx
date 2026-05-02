import type { Citation } from "../api";

interface CitationsPanelProps {
  citations: Citation[];
}

export default function CitationsPanel({ citations }: CitationsPanelProps) {
  if (citations.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
        Evidence
      </p>
      {citations.map((c) => (
        <div key={c.id} className="pl-3 border-l-2 border-gray-300">
          <p className="italic text-sm text-gray-600">&ldquo;{c.quote}&rdquo;</p>
          {c.rationale && (
            <p className="mt-1 text-xs text-gray-400">{c.rationale}</p>
          )}
          {c.segment_ids.length > 0 && (
            <p className="mt-1 font-mono text-[10px] text-gray-300">
              Segments: {c.segment_ids.join(", ")}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
