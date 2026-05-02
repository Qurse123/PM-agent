import { useState, useEffect, useCallback } from "react";
import { Link, useParams } from "wouter";
import { getProposals, approveAll } from "../api";
import type { Proposal, ApproveAllResult } from "../api";
import ProposalCard from "../components/ProposalCard";

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <svg
        className="animate-spin h-8 w-8 text-gray-400"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  );
}

export default function RunDetail() {
  const params = useParams<{ id: string }>();
  const runId = params.id ?? "";

  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approveAllLoading, setApproveAllLoading] = useState(false);
  const [approveAllResult, setApproveAllResult] = useState<ApproveAllResult | null>(null);

  const fetchProposals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProposals(runId);
      setProposals(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load proposals");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void fetchProposals();
  }, [fetchProposals]);

  async function handleApproveAll() {
    setApproveAllLoading(true);
    setApproveAllResult(null);
    try {
      const result = await approveAll(runId);
      setApproveAllResult(result);
      await fetchProposals();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve all failed");
    } finally {
      setApproveAllLoading(false);
    }
  }

  const pendingCount = proposals.filter((p) => p.status === "pending").length;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Nav */}
        <div className="mb-6">
          <Link
            href="/"
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            ← All runs
          </Link>
        </div>

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">
            Run{" "}
            <span className="font-mono text-gray-500">{runId.slice(0, 8)}</span>
          </h1>
        </div>

        {/* Summary bar */}
        {!loading && !error && (
          <div className="mb-5 flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {pendingCount > 0 ? (
                <>
                  <span className="font-semibold">{pendingCount}</span> pending proposal{pendingCount !== 1 ? "s" : ""}
                </>
              ) : (
                "No pending proposals"
              )}
            </p>

            <div className="flex items-center gap-3">
              {approveAllResult && (
                <span className="text-sm text-green-700">
                  ✓ {approveAllResult.approved} approved
                  {approveAllResult.failed > 0 && `, ${approveAllResult.failed} failed`}
                </span>
              )}
              {pendingCount > 0 && (
                <button
                  onClick={handleApproveAll}
                  disabled={approveAllLoading}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {approveAllLoading ? (
                    <>
                      <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Approving…
                    </>
                  ) : (
                    "Approve All"
                  )}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && <Spinner />}

        {/* Empty */}
        {!loading && !error && proposals.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-white px-8 py-16 text-center">
            <p className="text-gray-400 text-sm">No proposals for this run</p>
          </div>
        )}

        {/* Proposals */}
        {!loading && proposals.length > 0 && (
          <div className="space-y-4">
            {proposals.map((p) => (
              <ProposalCard
                key={p.id}
                proposal={p}
                runId={runId}
                onAction={fetchProposals}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
