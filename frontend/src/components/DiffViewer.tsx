interface DiffViewerProps {
  before: Record<string, unknown> | null;
  after: Record<string, unknown>;
}

function formatFieldName(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const PRIORITY_MAP: Record<string, string> = {
  "0": "No priority",
  "1": "Urgent",
  "2": "High",
  "3": "Medium",
  "4": "Low",
};

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (key === "priority" || key === "priorityLabel") {
    const mapped = PRIORITY_MAP[String(value)];
    if (mapped) return mapped;
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if (obj.name) return String(obj.name);
    return JSON.stringify(value);
  }
  const str = String(value).trim();
  return str || "—";
}

function isChanged(key: string, before: Record<string, unknown> | null, after: Record<string, unknown>): boolean {
  const bVal = before ? formatValue(key, before[key]) : "—";
  const aVal = formatValue(key, after[key]);
  return bVal !== aVal;
}

export default function DiffViewer({ before, after }: DiffViewerProps) {
  const keys = Object.keys(after).filter((key) =>
    isChanged(key, before, after)
  );

  if (keys.length === 0) {
    return (
      <p className="text-xs text-slate-400 italic">No field differences detected.</p>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden text-sm">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            <th className="py-2 px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400 w-32">
              Field
            </th>
            <th className="py-2 px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400 w-1/2">
              Before
            </th>
            <th className="py-2 px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400 w-1/2">
              After
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {keys.map((key) => {
            const beforeVal = before ? formatValue(key, before[key]) : "—";
            const afterVal = formatValue(key, after[key]);
            return (
              <tr key={key}>
                <td className="py-2.5 px-3 text-sm text-slate-600 font-medium align-top">
                  {formatFieldName(key)}
                </td>
                <td className="py-2.5 px-3 align-top" style={{ backgroundColor: "#fff0f0" }}>
                  <span className="text-[13px] text-red-700 leading-relaxed">{beforeVal}</span>
                </td>
                <td className="py-2.5 px-3 align-top" style={{ backgroundColor: "#f0fff4" }}>
                  <span className="text-[13px] text-emerald-700 leading-relaxed">{afterVal}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
