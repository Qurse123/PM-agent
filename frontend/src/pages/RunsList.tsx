import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "wouter";
import { getRuns, deleteRun, createRun, analyzeRun, listTeams } from "../api";
import type { Run, LinearTeam } from "../api";
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
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${pill}`}>
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

function ProcessingCard({ run }: { run: Run }) {
  const meetingName = run.title ?? run.conference_record_id;
  return (
    <div className="relative bg-white rounded-xl border border-blue-200 shadow-sm overflow-hidden">
      {/* animated shimmer bar */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-200 via-indigo-400 to-blue-200 animate-[shimmer_1.8s_ease-in-out_infinite] bg-[length:200%_100%]" />
      <div className="px-4 pt-4 pb-4">
        <div className="flex items-center gap-2 mb-2">
          <svg className="animate-spin h-3.5 w-3.5 text-blue-500 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-xs font-medium text-blue-600">Generating proposals…</span>
        </div>
        <p className="text-lg font-semibold text-slate-700 leading-snug">{meetingName}</p>
        <div className="mt-3 space-y-1.5">
          <div className="h-2.5 bg-slate-100 rounded-full w-full animate-pulse" />
          <div className="h-2.5 bg-slate-100 rounded-full w-4/5 animate-pulse" />
          <div className="h-2.5 bg-slate-100 rounded-full w-3/5 animate-pulse" />
        </div>
      </div>
    </div>
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
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 px-2 py-0.5 text-xs font-medium">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              All reviewed
            </span>
          )}
          {pendingCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 ring-1 ring-amber-200 px-2 py-0.5 text-xs font-medium">
              {pendingCount} pending
            </span>
          )}
        </div>

        {/* Meeting name */}
        <p className="text-lg font-semibold text-slate-900 mb-2 leading-snug pr-2">
          {meetingName}
        </p>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-2.5 text-sm text-slate-400">
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
      <div className={`flex items-center gap-2 mb-4 pb-3 border-b-2 ${accent}`}>
        <span className="text-base font-semibold text-slate-700">{title}</span>
        <span className="inline-flex items-center justify-center rounded-full bg-slate-100 text-slate-500 text-sm font-medium px-2.5 py-0.5 min-w-[24px]">
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
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitProgress, setSubmitProgress] = useState<{ done: number; total: number } | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [teams, setTeams] = useState<LinearTeam[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>("");
  const titleRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const ACCEPTED_EXTS = new Set([".txt", ".vtt", ".srt", ".md"]);

  const fetchRuns = useCallback(() => {
    getRuns()
      .then(setRuns)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load runs"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchRuns(); }, [fetchRuns]);

  useEffect(() => {
    listTeams().then(setTeams).catch(() => {});
  }, []);

  // Poll while any run is still processing
  useEffect(() => {
    const hasProcessing = runs.some((r) => r.status === "analyzing" || r.status === "ingesting");
    if (!hasProcessing) return;
    const id = setInterval(fetchRuns, 4000);
    return () => clearInterval(id);
  }, [runs, fetchRuns]);

  function handleDelete(id: string) {
    setRuns((prev) => prev.filter((r) => r.id !== id));
  }

  function openPanel() {
    setPanelOpen(true);
    setNewTitle("");
    setUploadedFiles([]);
    setSubmitError(null);
    setSubmitProgress(null);
    setSelectedTeamId("");
    setTimeout(() => titleRef.current?.focus(), 50);
  }

  function closePanel() {
    setPanelOpen(false);
    setSubmitError(null);
    setSubmitProgress(null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setUploadedFiles(files);
    e.target.value = "";
  }

  function handleFolderChange(e: React.ChangeEvent<HTMLInputElement>) {
    const all = Array.from(e.target.files ?? []);
    const transcripts = all.filter((f) => {
      const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
      return ACCEPTED_EXTS.has(ext);
    });
    if (transcripts.length) setUploadedFiles(transcripts);
    else setSubmitError(`No .txt / .vtt / .srt / .md files found in that folder`);
    e.target.value = "";
  }

  function readFileText(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve((ev.target?.result as string) ?? "");
      reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
      reader.readAsText(file);
    });
  }

  function titleFromFile(file: File): string {
    return file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ").trim();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    const isSingle = uploadedFiles.length === 1;
    setSubmitProgress({ done: 0, total: uploadedFiles.length });
    try {
      for (let i = 0; i < uploadedFiles.length; i++) {
        const file = uploadedFiles[i];
        const text = await readFileText(file);
        const title = isSingle && newTitle.trim() ? newTitle.trim() : titleFromFile(file);
        const run = await createRun({ title, transcript_text: text.trim(), linear_team_id: selectedTeamId || null });
        analyzeRun(run.id).catch(() => { /* worker may not be running; run stays in ready */ });
        setSubmitProgress({ done: i + 1, total: uploadedFiles.length });
      }
      setPanelOpen(false);
      setLoading(true);
      fetchRuns();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create run");
    } finally {
      setSubmitting(false);
      setSubmitProgress(null);
    }
  }

  const processing = runs.filter((r) => r.status === "analyzing" || r.status === "ingesting");
  const toReview = runs.filter((r) => r.status === "ready" && (r.pending_proposal_count > 0 || r.proposal_count === 0));
  const reviewed = runs.filter((r) => r.status === "ready" && r.proposal_count > 0 && r.pending_proposal_count === 0);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-screen-2xl mx-auto px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-indigo-600">
              <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <span className="text-lg font-semibold text-slate-900">PM Agent</span>
            <span className="text-slate-300">·</span>
            <span className="text-base text-slate-400">AI ticket proposal review</span>
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

      <main className="max-w-screen-2xl mx-auto px-8 py-10">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">Analysis runs</h1>
          <p className="mt-1 text-base text-slate-500">Each run analyzes a meeting transcript and proposes ticket updates.</p>
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
              {/* Title field — only for single-file uploads */}
              {uploadedFiles.length <= 1 && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">
                    Meeting title {uploadedFiles.length === 0 && <span className="text-red-500">*</span>}
                    {uploadedFiles.length === 1 && <span className="text-slate-400">(optional — defaults to filename)</span>}
                  </label>
                  <input
                    ref={titleRef}
                    type="text"
                    value={newTitle}
                    onChange={(e) => {
                      const val = e.target.value;
                      setNewTitle(val);
                      const lower = val.toLowerCase();
                      const match = teams.find(
                        (t) => lower.includes(t.name.toLowerCase()) || lower.includes(t.key.toLowerCase())
                      );
                      setSelectedTeamId(match ? match.linear_team_id : "");
                    }}
                    placeholder="Q3 Engineering Planning"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required={uploadedFiles.length === 0}
                  />
                </div>
              )}
              {teams.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">
                    Team board
                    <span className="ml-1.5 text-slate-400 font-normal">(auto-matched from title)</span>
                  </label>
                  <select
                    value={selectedTeamId}
                    onChange={(e) => setSelectedTeamId(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value="">All teams (no filter)</option>
                    {teams.map((t) => (
                      <option key={t.linear_team_id} value={t.linear_team_id}>
                        {t.name} ({t.key})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Transcript{uploadedFiles.length > 1 ? "s" : ""} <span className="text-red-500">*</span>
                  {uploadedFiles.length > 1 && (
                    <span className="ml-1.5 text-slate-400 font-normal">Each file creates a separate run</span>
                  )}
                </label>
                {/* Hidden inputs */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.vtt,.srt,.md,text/plain"
                  multiple
                  className="hidden"
                  onChange={handleFileChange}
                />
                <input
                  ref={folderInputRef}
                  type="file"
                  className="hidden"
                  onChange={handleFolderChange}
                  // @ts-expect-error — webkitdirectory is not in React's typedefs
                  webkitdirectory=""
                />

                {uploadedFiles.length > 0 ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 divide-y divide-slate-100">
                    {uploadedFiles.map((f) => (
                      <div key={f.name} className="flex items-center gap-2 px-4 py-2.5">
                        <svg className="h-4 w-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                        </svg>
                        <span className="text-sm text-slate-700 truncate flex-1">{f.name}</span>
                        <span className="text-xs text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                      </div>
                    ))}
                    <div className="px-4 py-2.5 flex gap-3">
                      <button type="button" onClick={() => fileInputRef.current?.click()} className="text-xs text-indigo-600 hover:text-indigo-800">
                        Change files
                      </button>
                      <span className="text-slate-300">·</span>
                      <button type="button" onClick={() => folderInputRef.current?.click()} className="text-xs text-indigo-600 hover:text-indigo-800">
                        Change folder
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="rounded-lg border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-white hover:bg-indigo-50 px-4 py-8 text-center transition-colors"
                    >
                      <svg className="mx-auto h-7 w-7 text-slate-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      <p className="text-sm font-medium text-slate-600">Upload files</p>
                      <p className="text-xs text-slate-400 mt-1">.txt, .vtt, .srt, .md</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => folderInputRef.current?.click()}
                      className="rounded-lg border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-white hover:bg-indigo-50 px-4 py-8 text-center transition-colors"
                    >
                      <svg className="mx-auto h-7 w-7 text-slate-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                      </svg>
                      <p className="text-sm font-medium text-slate-600">Upload folder</p>
                      <p className="text-xs text-slate-400 mt-1">Scans for transcript files</p>
                    </button>
                  </div>
                )}
              </div>
              {submitError && <p className="text-sm text-red-600">{submitError}</p>}
              <div className="flex items-center justify-end gap-3 pt-1">
                <button type="button" onClick={closePanel} className="rounded-lg px-3.5 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 transition-colors">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || uploadedFiles.length === 0}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                >
                  {submitting && submitProgress
                    ? <><SmallSpinner /> Creating {submitProgress.done + 1} of {submitProgress.total}…</>
                    : uploadedFiles.length > 1
                      ? `Create ${uploadedFiles.length} runs`
                      : "Create run"}
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
          <div className="grid grid-cols-3 gap-6">
            {/* Processing column — custom render with ProcessingCard */}
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b-2 border-blue-400">
                <span className="text-base font-semibold text-slate-700">Processing</span>
                <span className="inline-flex items-center justify-center rounded-full bg-slate-100 text-slate-500 text-sm font-medium px-2.5 py-0.5 min-w-[24px]">
                  {processing.length}
                </span>
              </div>
              <div className="space-y-3 flex-1">
                {processing.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-4 py-10 text-center">
                    <p className="text-xs text-slate-400">Uploaded runs appear here</p>
                  </div>
                ) : (
                  processing.map((run) => <ProcessingCard key={run.id} run={run} />)
                )}
              </div>
            </div>
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
