interface DiffViewerProps {
  before: Record<string, unknown> | null;
  after: Record<string, unknown>;
}

function formatFieldName(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DiffViewer({ before, after }: DiffViewerProps) {
  const keys = Object.keys(after);

  return (
    <div className="overflow-hidden rounded border border-gray-200 text-sm">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="py-2 px-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide w-auto whitespace-nowrap">
              Field
            </th>
            <th className="py-2 px-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide w-1/2">
              Before
            </th>
            <th className="py-2 px-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide w-1/2">
              After
            </th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key, i) => {
            const beforeVal = before ? before[key] : undefined;
            const afterVal = after[key];
            return (
              <tr
                key={key}
                className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}
              >
                <td className="py-2 px-3 font-medium text-gray-700 whitespace-nowrap border-b border-gray-100">
                  {formatFieldName(key)}
                </td>
                <td
                  className="py-2 px-3 border-b border-gray-100"
                  style={{ backgroundColor: "#fee2e2" }}
                >
                  <span className="text-red-700 break-words">
                    {formatValue(beforeVal)}
                  </span>
                </td>
                <td
                  className="py-2 px-3 border-b border-gray-100"
                  style={{ backgroundColor: "#dcfce7" }}
                >
                  <span className="text-green-700 break-words">
                    {formatValue(afterVal)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
