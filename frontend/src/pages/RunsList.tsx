import { useState, useEffect, useRef } from "react";
import { Link } from "wouter";
import { getRuns, deleteRun, createRun } from "../api";
import type { Run } from "../api";
import { relativeTime, formatMeetingName } from "../lib/utils";

const STATUS_DOT: Record<string, string> = {
  ingesting: "bg-slate-400",
  ready:     "bg-emerald-500",
  analyzing: "bg-blue-500",
  failed:    "bg-red-500",
};

const STATUS_PILL: Record<string, string> = {
  ingesting: "bg-slate-100 text-slate-600",
  ready:     "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  analyzing: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
  failed:    "bg-red-50 text-red-700 ring-1 ring-red-200",
};

function StatusPill({ status }: { status: string }) {
  const dot  = STATUS_DOT[status]  ?? "bg-slate-400";
  const pill = STATUS_PILL[status] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${pill}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}

function Spinner() {
  return (
    <div className="col-span-2 flex items-center justify-center py-24">
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

interface RunCardProps {
  run: Run;
  onDelete: (id: string) => void;
}

function RunCard({ run, onDelete }: RunCardProps) {
  const [deleting, setDeleting] = useState(false);
  const meetingName   = run.title ?? formatMeetingName(run.conference_record_id);
  const proposalCount = run.proposal_count;
  const pendingCount  = run.pending_proposal_count;
  const allReviewed   = proposalCount > 0 && pendingCount === 0;

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete run "${meetingName}"?`)) return;
    setDeleting(true);
    try {
      await deleteRun(run.id);
      onDelete(run.id);
    } catch {
      setDeleting(false);
    }
  }

  return (
    <div className="group relative bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-slate-300 transition-all duration-150">
      {/* Delete button — top-right, visible on hover */}
      <button
        onClick={handleDelete}
        disabled={deleting}
        title="Delete run"
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-slate-300 hover:text-red-400 hover:bg-red-50 disabled:opacity-30"
      >
        {deleting ? (
          <SmallSpinner />
        ) : (
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
        )}
      </button>

      <div className="px-4 pt-4 pb-3.5 pr-8">
        {/* Badges */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <StatusPill status={run.status} />
          {allReviewed && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 px-2 py-0.5 text-[11px] font-medium">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              All reviewed
            </span>
          )}
          {pendingCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 ring-1 ring-amber-200 px-2 py-0.5 text-[11px] font-medium">
              {pendingCount} pending
            </span>
          )}
        </div>

        {/* Meeting name */}
        <p className="text-[15px] font-semibold text-slate-900 mb-2 leading-snug pr-2">
          {meetingName}
        </p>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs text-slate-400">
          {proposalCount > 0 && (
            <span className="flex items-center gap-1">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
              </svg>
              {proposalCount} proposal{proposalCount !== 1 ? "s" : ""}
            </span>
          )}
          <span className="flex items-center gap-1">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {relativeTime(run.created_at)}
          </span>
        </div>
      </div>

      {/* Review CTA */}
      <div className="px-4 pb-4">
        <Link
          href={`/runs/${run.id}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 transition-colors shadow-sm w-full justify-center"
        >
          Review
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </Link>
      </div>
    </div>
  );
}

function Column({
  title,
  count,
  accent,
  runs,
  onDelete,
  emptyText,
}: {
  title: string;
  count: number;
  accent: string;
  runs: Run[];
  onDelete: (id: string) => void;
  emptyText: string;
}) {
  return (
    <div className="flex flex-col min-w-0">
      <div className={`flex items-center gap-2 mb-3 pb-2.5 border-b-2 ${accent}`}>
        <span className="text-sm font-semibold text-slate-700">{title}</span>
        <span className="inline-flex items-center justify-center rounded-full bg-slate-100 text-slate-500 text-xs font-medium px-2 py-0.5 min-w-[20px]">
          {count}
        </span>
      </div>
      <div className="space-y-3 flex-1">
        {runs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-4 py-10 text-center">
            <p className="text-xs text-slate-400">{emptyText}</p>
          </div>
        ) : (
          runs.map((run) => (
            <RunCard key={run.id} run={run} onDelete={onDelete} />
          ))
        )}
      </div>
    </div>
  );
}

export default function RunsList() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newTranscript, setNewTranscript] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function fetchRuns() {
    getRuns()
      .then(setRuns)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load runs"))
      .finally(() => setLoading(false));
  }

  useEffect(() => { fetchRuns(); }, []);

  function handleDelete(id: string) {
    setRuns((prev) => prev.filter((r) => r.id !== id));
  }

  function openPanel() {
    setPanelOpen(true);
    setNewTitle("");
    setNewTranscript("");
    setUploadedFile(null);
    setSubmitError(null);
    setTimeout(() => titleRef.current?.focus(), 50);
  }

  function closePanel() {
    setPanelOpen(false);
    setSubmitError(null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setNewTranscript((ev.target?.result as string) ?? "");
    reader.readAsText(file);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createRun({ title: newTitle.trim(), transcript_text: newTranscript.trim() });
      setPanelOpen(false);
      setLoading(true);
      fetchRuns();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create run");
    } finally {
      setSubmitting(false);
    }
  }

  const toReview = runs.filter((r) => r.pending_proposal_count > 0 || r.proposal_count === 0);
  const reviewed = runs.filter((r) => r.proposal_count > 0 && r.pending_proposal_count === 0);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-indigo-600">
              <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <span className="font-semibold text-slate-900">PM Agent</span>
            <span className="text-slate-300">·</span>
            <span className="text-sm text-slate-400">AI ticket proposal review</span>
          </div>
          <button
            onClick={openPanel}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors shadow-sm"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New run
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-slate-900">Analysis runs</h1>
          <p className="mt-0.5 text-sm text-slate-500">Each run analyzes a meeting transcript and proposes ticket updates.</p>
        </div>

        {/* New run panel */}
        {panelOpen && (
          <div className="mb-6 rounded-xl border border-indigo-200 bg-white shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">New analysis run</h2>
              <button onClick={closePanel} className="text-slate-400 hover:text-slate-600 transition-colors">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Meeting title <span className="text-red-500">*</span></label>
                <input
                  ref={titleRef}
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="Q3 Engineering Planning"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Transcript <span className="text-red-500">*</span></label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.vtt,.srt,.md,text/plain"
                  className="hidden"
                  onChange={handleFileChange}
                />
                {uploadedFile ? (
                  <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <svg className="h-4 w-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      <span className="text-sm text-slate-700 truncate">{uploadedFile.name}</span>
                      <span className="text-xs text-slate-400 shrink-0">({(uploadedFile.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button type="button" onClick={() => fileInputRef.current?.click()} className="text-xs text-indigo-600 hover:text-indigo-800 shrink-0 ml-3">
                      Change
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full rounded-lg border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-white hover:bg-indigo-50 px-4 py-8 text-center transition-colors"
                  >
                    <svg className="mx-auto h-8 w-8 text-slate-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                    </svg>
                    <p className="text-sm font-medium text-slate-600">Click to upload transcript</p>
                    <p className="text-xs text-slate-400 mt-1">.txt, .vtt, .srt, .md</p>
                  </button>
                )}
              </div>
              {submitError && <p className="text-sm text-red-600">{submitError}</p>}
              <div className="flex items-center justify-end gap-3 pt-1">
                <button type="button" onClick={closePanel} className="rounded-lg px-3.5 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 transition-colors">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !newTitle.trim() || !uploadedFile}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                >
                  {submitting ? <><SmallSpinner /> Creating…</> : "Create run"}
                </button>
              </div>
            </form>
          </div>
        )}

        {loading && (
          <div className="grid grid-cols-2 gap-6">
            <Spinner />
          </div>
        )}

        {error && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-5 py-4 flex items-start gap-3">
            <svg className="h-4 w-4 text-red-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-red-800">Could not load runs</p>
              <p className="text-xs text-red-500 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {!loading && !error && (
          <div className="grid grid-cols-2 gap-6">
            <Column
              title="To Review"
              count={toReview.length}
              accent="border-amber-400"
              runs={toReview}
              onDelete={handleDelete}
              emptyText="No runs awaiting review"
            />
            <Column
              title="Reviewed"
              count={reviewed.length}
              accent="border-emerald-400"
              runs={reviewed}
              onDelete={handleDelete}
              emptyText="Reviewed runs will appear here"
            />
          </div>
        )}
      </main>
    </div>
  );
}
