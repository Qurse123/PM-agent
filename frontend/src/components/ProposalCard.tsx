import { useState } from "react";
import type { Proposal } from "../api";
import { approveProposal, denyProposal } from "../api";
import DiffViewer from "./DiffViewer";
import CitationsPanel from "./CitationsPanel";
import DenyModal from "./DenyModal";
import { getTicketTitle, getProjectName, getAssigneeName, getIssueIdentifier } from "../lib/utils";

interface ProposalCardProps {
  proposal: Proposal;
  runId: string;
  onAction: () => void;
}

function SmallSpinner() {
  return (
    <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

const OPERATION_COLORS: Record<string, { bg: string; text: string }> = {
  create: { bg: "#e6f9f1", text: "#0a7c4e" },
  update: { bg: "#e8f0fe", text: "#2c57c7" },
};

const STATUS_PILL: Record<string, string> = {
  pending:  "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  approved: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  applied:  "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  denied:   "bg-orange-50 text-orange-700 ring-1 ring-orange-200",
  failed:   "bg-red-50 text-red-700 ring-1 ring-red-200",
};

const CARD_LEFT: Record<string, string> = {
  approved: "border-l-emerald-400",
  applied:  "border-l-emerald-400",
  denied:   "border-l-orange-400",
  failed:   "border-l-red-400",
  pending:  "border-l-slate-200",
};

export default function ProposalCard({ proposal, runId, onAction }: ProposalCardProps) {
  const [actionLoading, setActionLoading] = useState<"approve" | "deny" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDenyForm, setShowDenyForm] = useState(false);
  const [diffOpen, setDiffOpen] = useState(true);
  const [citationsOpen, setCitationsOpen] = useState(false);

  const title     = getTicketTitle(proposal.after);
  const project   = getProjectName(proposal.after);
  const assignee  = getAssigneeName(proposal.after);
  const issueId   = getIssueIdentifier(proposal.after);
  const opStyle   = OPERATION_COLORS[proposal.operation] ?? { bg: "#f1f5f9", text: "#475569" };
  const cardLeft  = CARD_LEFT[proposal.status] ?? CARD_LEFT.pending;

  async function handleApprove() {
    setActionLoading("approve");
    setError(null);
    try {
      await approveProposal(runId, proposal.id);
      onAction();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
      setActionLoading(null);
    }
  }

  async function handleDeny(reason: string, category: string, disputedIds: string[]) {
    setActionLoading("deny");
    setError(null);
    try {
      await denyProposal(runId, proposal.id, { reason, category, disputed_segment_ids: disputedIds });
      setShowDenyForm(false);
      onAction();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deny failed");
      setActionLoading(null);
    }
  }

  const diffKeys = Object.keys(proposal.after).length;

  return (
    <div className={`rounded-xl border border-l-[3px] border-slate-200 bg-white shadow-sm overflow-hidden ${cardLeft}`}>

      {/* ── Card header ── */}
      <div className="px-5 pt-4 pb-3.5">
        {/* Row 1: operation badge + target + status */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <span
              className="rounded px-1.5 py-0.5 text-[11px] font-bold uppercase tracking-wide"
              style={{ backgroundColor: opStyle.bg, color: opStyle.text }}
            >
              {proposal.operation}
            </span>
            <span className="text-xs text-slate-400">{proposal.target}</span>
            {issueId && (
              <span className="font-mono text-[11px] bg-slate-100 text-slate-500 rounded px-1.5 py-0.5">
                {issueId}
              </span>
            )}
          </div>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_PILL[proposal.status] ?? "bg-slate-100 text-slate-600"}`}>
            {proposal.status}
          </span>
        </div>

        {/* Row 2: ticket title */}
        <p className="text-[15px] font-semibold text-slate-900 leading-snug mb-2">
          {title ?? <span className="text-slate-400 italic font-normal">Untitled proposal</span>}
        </p>

        {/* Row 3: project + assignee meta */}
        {(project || assignee) && (
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            {project && (
              <span className="flex items-center gap-1">
                <svg className="h-3.5 w-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
                <span className="font-medium text-violet-700">{project}</span>
              </span>
            )}
            {assignee && (
              <span className="flex items-center gap-1.5">
                <span className="inline-flex h-4.5 w-4.5 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 text-[9px] font-bold px-1">
                  {assignee.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()}
                </span>
                {assignee}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Field changes (collapsible) ── */}
      <div className="border-t border-slate-100">
        <button
          onClick={() => setDiffOpen(v => !v)}
          className="w-full flex items-center justify-between px-5 py-2.5 text-xs font-medium text-slate-500 hover:bg-slate-50 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 3M21 7.5H7.5" />
            </svg>
            Field changes
            <span className="text-slate-300 font-normal">({diffKeys})</span>
          </span>
          <svg className={`h-3.5 w-3.5 text-slate-400 transition-transform ${diffOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
        {diffOpen && (
          <div className="px-5 pb-4">
            <DiffViewer before={proposal.before} after={proposal.after} />
          </div>
        )}
      </div>

      {/* ── Transcript excerpts (collapsible) ── */}
      {proposal.citations.length > 0 && (
        <div className="border-t border-slate-100">
          <button
            onClick={() => setCitationsOpen(v => !v)}
            className="w-full flex items-center justify-between px-5 py-2.5 text-xs font-medium text-slate-500 hover:bg-slate-50 transition-colors"
          >
            <span className="flex items-center gap-1.5">
              <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
              </svg>
              {proposal.citations.length} transcript excerpt{proposal.citations.length !== 1 ? "s" : ""}
            </span>
            <svg className={`h-3.5 w-3.5 text-slate-400 transition-transform ${citationsOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {citationsOpen && (
            <div className="px-5 pb-4">
              <CitationsPanel citations={proposal.citations} />
            </div>
          )}
        </div>
      )}

      {/* ── Footer ── */}
      <div className="border-t border-slate-100 px-5 py-3">
        {error && (
          <p className="mb-2.5 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-1.5 border border-red-100">{error}</p>
        )}

        {proposal.status === "pending" ? (
          <div className="flex items-center gap-2">
            <button
              onClick={handleApprove}
              disabled={actionLoading !== null}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              {actionLoading === "approve"
                ? <><SmallSpinner /> Approving…</>
                : <><svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg> Approve</>}
            </button>
            <button
              onClick={() => setShowDenyForm(v => !v)}
              disabled={actionLoading !== null}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${showDenyForm ? "bg-slate-100 border-slate-300 text-slate-700" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"}`}
            >
              {actionLoading === "deny"
                ? <><SmallSpinner /> Denying…</>
                : <><svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg> Deny</>}
            </button>
          </div>
        ) : (
          <p className={`text-xs flex items-center gap-1.5 ${proposal.status === "approved" || proposal.status === "applied" ? "text-emerald-600" : proposal.status === "denied" ? "text-orange-600" : "text-slate-400"}`}>
            {(proposal.status === "approved" || proposal.status === "applied") && (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
            )}
            {proposal.status === "denied" && (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
            )}
            {proposal.status === "approved" || proposal.status === "applied"
              ? "This proposal was approved"
              : proposal.status === "denied"
              ? "This proposal was denied"
              : `Status: ${proposal.status}`}
          </p>
        )}

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
