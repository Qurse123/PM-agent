import { useState, useEffect, useCallback } from "react";
import { Link, useParams } from "wouter";
import { getProposals, getRun, approveAll } from "../api";
import type { Proposal, ApproveAllResult, Run } from "../api";
import ProposalCard from "../components/ProposalCard";
import { formatMeetingName, relativeTime, getProjectName } from "../lib/utils";

function Spinner() {
  return (
    <div className="flex items-center justify-center py-24">
      <svg className="animate-spin h-7 w-7 text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  );
}

function SmallSpinner() {
  return (
    <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export default function RunDetail() {
  const params = useParams<{ id: string }>();
  const runId = params.id ?? "";

  const [run, setRun] = useState<Run | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approveAllLoading, setApproveAllLoading] = useState(false);
  const [approveAllResult, setApproveAllResult] = useState<ApproveAllResult | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [proposalsData, runData] = await Promise.allSettled([
        getProposals(runId),
        getRun(runId),
      ]);
      if (proposalsData.status === "fulfilled") setProposals(proposalsData.value);
      else throw proposalsData.reason as Error;
      if (runData.status === "fulfilled") setRun(runData.value);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  const refreshProposals = useCallback(async () => {
    try {
      const data = await getProposals(runId);
      setProposals(data);
    } catch { /* silent refresh */ }
  }, [runId]);

  useEffect(() => { void fetchData(); }, [fetchData]);

  async function handleApproveAll() {
    setApproveAllLoading(true);
    setApproveAllResult(null);
    try {
      const result = await approveAll(runId);
      setApproveAllResult(result);
      await refreshProposals();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve all failed");
    } finally {
      setApproveAllLoading(false);
    }
  }

  const pendingCount = proposals.filter((p) => p.status === "pending").length;
  const allReviewed  = proposals.length > 0 && pendingCount === 0;

  const folderName = (() => {
    for (const p of proposals) {
      const pn = getProjectName(p.after);
      if (pn) return pn;
    }
    return null;
  })();

  const meetingName = run?.title ?? formatMeetingName(run?.conference_record_id ?? runId);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 h-14 flex items-center gap-2">
          <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-indigo-600 shrink-0">
            <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <span className="font-semibold text-slate-900">PM Agent</span>
          <svg className="h-4 w-4 text-slate-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <Link href="/" className="text-sm text-slate-500 hover:text-slate-700 transition-colors shrink-0">
            All runs
          </Link>
          <svg className="h-4 w-4 text-slate-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <span className="text-sm font-medium text-slate-800 truncate">{meetingName}</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {/* Page title + meta */}
        {!loading && (
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900 mb-3">{meetingName}</h1>
            <div className="flex flex-wrap items-center gap-2">
              {proposals.length > 0 && (
                <span className="flex items-center gap-1.5 text-sm text-slate-500">
                  <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
                  </svg>
                  {proposals.length} proposal{proposals.length !== 1 ? "s" : ""}
                </span>
              )}

              {allReviewed && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 px-2.5 py-0.5 text-xs font-medium">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  All reviewed
                </span>
              )}
              {pendingCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 ring-1 ring-amber-200 px-2.5 py-0.5 text-xs font-medium">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                  {pendingCount} pending
                </span>
              )}

              {folderName && (
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 text-violet-700 ring-1 ring-violet-200 px-2.5 py-0.5 text-xs font-medium">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                  </svg>
                  {folderName}
                </span>
              )}

              {run?.created_at && (
                <span className="flex items-center gap-1 text-xs text-slate-400">
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Analyzed {relativeTime(run.created_at)}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Toolbar */}
        {!loading && !error && pendingCount > 0 && (
          <div className="mb-5 flex items-center justify-between">
            <div />
            <div className="flex items-center gap-3">
              {approveAllResult && (
                <span className="text-sm text-emerald-700 font-medium">
                  ✓ {approveAllResult.approved} approved
                  {approveAllResult.failed > 0 && (
                    <span className="text-red-600">, {approveAllResult.failed} failed</span>
                  )}
                </span>
              )}
              <button
                onClick={handleApproveAll}
                disabled={approveAllLoading}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              >
                {approveAllLoading ? <><SmallSpinner /> Approving…</> : "Approve all"}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-5 rounded-xl bg-red-50 border border-red-200 px-5 py-4 text-sm text-red-700">
            {error}
          </div>
        )}
        {loading && <Spinner />}
        {!loading && !error && proposals.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-8 py-20 text-center">
            <p className="text-sm font-medium text-slate-500">No proposals for this run</p>
          </div>
        )}

        {!loading && proposals.length > 0 && (
          <div className="space-y-4">
            {proposals.map((p) => (
              <ProposalCard
                key={p.id}
                proposal={p}
                runId={runId}
                onAction={refreshProposals}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
