import { useState } from "react";
import type { Citation } from "../api";

interface DenyModalProps {
  citations: Citation[];
  onSubmit: (
    reason: string,
    category: string,
    disputedIds: string[]
  ) => void;
  onCancel: () => void;
}

const CATEGORIES = [
  { label: "Wrong issue", value: "wrong_issue" },
  { label: "Wrong field", value: "wrong_field" },
  { label: "Transcript misread", value: "transcript_misread" },
  { label: "Missing context", value: "missing_context" },
  { label: "Policy", value: "policy" },
];

export default function DenyModal({
  citations,
  onSubmit,
  onCancel,
}: DenyModalProps) {
  const [reason, setReason] = useState("");
  const [category, setCategory] = useState("wrong_issue");
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  function toggleCitation(segmentIds: string[], checked: boolean) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      segmentIds.forEach((id) => {
        if (checked) next.add(id);
        else next.delete(id);
      });
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(reason, category, Array.from(checkedIds));
  }

  return (
    <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="mb-3 text-sm font-semibold text-red-700">Deny Proposal</p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Why is this proposal wrong? <span className="text-red-500">*</span>
          </label>
          <textarea
            className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-300 resize-none"
            rows={3}
            placeholder="Explain the issue..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Category
          </label>
          <select
            className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-red-300"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
        </div>

        {citations.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">
              Which quotes are incorrect? (optional)
            </label>
            <div className="space-y-2">
              {citations.map((c) => {
                const isChecked = c.segment_ids.some((id) =>
                  checkedIds.has(id)
                );
                return (
                  <label
                    key={c.id}
                    className="flex items-start gap-2 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 rounded border-gray-300 accent-red-500"
                      checked={isChecked}
                      onChange={(e) =>
                        toggleCitation(c.segment_ids, e.target.checked)
                      }
                    />
                    <span className="text-xs italic text-gray-600">
                      &ldquo;{c.quote}&rdquo;
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <button
            type="submit"
            disabled={!reason.trim()}
            className="px-4 py-1.5 rounded text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Submit Denial
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-1.5 rounded text-sm font-medium border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
