import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatMeetingName(conferenceRecordId: string): string {
  if (!conferenceRecordId) return "Untitled Meeting";
  const isUuid = /^[0-9a-f-]{36}$/i.test(conferenceRecordId);
  if (isUuid) return `Meeting ${conferenceRecordId.slice(0, 8).toUpperCase()}`;
  return conferenceRecordId;
}

function extractFromRecord(
  record: Record<string, unknown>,
  keys: string[]
): string | null {
  for (const key of keys) {
    const val = record[key];
    if (val && typeof val === "string" && val.trim()) return val.trim();
  }
  return null;
}

export function getTicketTitle(after: Record<string, unknown>): string | null {
  return extractFromRecord(after, ["title", "name", "summary", "description"]);
}

export function getProjectName(after: Record<string, unknown>): string | null {
  return extractFromRecord(after, [
    "project", "project_name", "projectName", "team", "teamName", "team_name",
  ]);
}

export function getAssigneeName(after: Record<string, unknown>): string | null {
  return extractFromRecord(after, [
    "assignee", "assignee_name", "assigneeName", "assigned_to", "owner",
  ]);
}

export function getIssueIdentifier(after: Record<string, unknown>): string | null {
  return extractFromRecord(after, ["identifier", "issue_id", "key", "number"]);
}
