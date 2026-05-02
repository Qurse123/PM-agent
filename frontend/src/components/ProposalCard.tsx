import { useState } from "react";
import type { Proposal } from "../api";
import { approveProposal, denyProposal } from "../api";
import DiffViewer from "./DiffViewer";
import CitationsPanel from "./CitationsPanel";
import DenyModal from "./DenyModal";

interface ProposalCardProps {
  proposal: Proposal;
  runId: string;
  onAction: () => void;
}

function OperationBadge({ operation }: { operation: string }) {
  const styles =
    operation === "create"
      ? "bg-green-100 text-green-700"
      : "bg-blue-100 text-blue-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${styles}`}>
      {operation}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-700",
    approved: "bg-green-100 text-green-700",
    applied: "bg-green-100 text-green-700",
    denied: "bg-orange-100 text-orange-700",
    failed: "bg-red-100 text-red-700",
  };
  const cls = styles[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      {status}
    </span>
  );
}

function cardBorderClass(status: string): string {
  if (status === "approved" || status === "applied") return "border-l-4 border-l-green-400";
  if (status === "denied") return "border-l-4 border-l-orange-400";
  return "border-l-4 border-l-transparent";
}

function cardBgClass(status: string): string {
  if (status === "approved" || status === "applied") return "bg-green-50/30";
  if (status === "denied") return "bg-red-50/30";
  return "bg-white";
}

export default function ProposalCard({ proposal, runId, onAction }: ProposalCardProps) {
  const [loading, setLoading] = useState<"approve" | "deny" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDenyForm, setShowDenyForm] = useState(false);

  async function handleApprove() {
    setLoading("approve");
    setError(null);
    try {
      await approveProposal(runId, proposal.id);
      onAction();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setLoading(null);
    }
  }

  async function handleDeny(reason: string, category: string, disputedIds: string[]) {
    setLoading("deny");
    setError(null);
    try {
      await denyProposal(runId, proposal.id, {
        reason,
        category,
        disputed_segment_ids: disputedIds,
      });
      setShowDenyForm(false);
      onAction();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deny failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div
      className={`rounded-lg border border-gray-200 shadow-sm overflow-hidden ${cardBorderClass(proposal.status)} ${cardBgClass(proposal.status)}`}
    >
      <div className="px-4 py-3">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <OperationBadge operation={proposal.operation} />
            <span className="text-sm text-gray-500">{proposal.target}</span>
          </div>
          <StatusBadge status={proposal.status} />
        </div>

        {/* Diff */}
        <div className="mb-3">
          <DiffViewer before={proposal.before} after={proposal.after} />
        </div>

        {/* Citations */}
        {proposal.citations.length > 0 && (
          <div className="mb-3">
            <CitationsPanel citations={proposal.citations} />
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="mb-2 text-xs text-red-600 bg-red-50 rounded px-2 py-1">{error}</p>
        )}

        {/* Actions */}
        {proposal.status === "pending" && (
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleApprove}
              disabled={loading !== null}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading === "approve" ? (
                <>
                  <Spinner />
                  Approving…
                </>
              ) : (
                "Approve"
              )}
            </button>
            <button
              onClick={() => setShowDenyForm((v) => !v)}
              disabled={loading !== null}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading === "deny" ? (
                <>
                  <Spinner />
                  Denying…
                </>
              ) : (
                "Deny"
              )}
            </button>
          </div>
        )}

        {/* Deny form */}
        {showDenyForm && proposal.status === "pending" && (
          <DenyModal
            citations={proposal.citations}
            onSubmit={handleDeny}
            onCancel={() => setShowDenyForm(false)}
          />
        )}
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-3 w-3"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
