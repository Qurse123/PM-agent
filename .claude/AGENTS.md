# PM Agent — Project Context

## What This Is

An AI-powered meeting agent that automatically keeps Jira and Linear tickets up to date using Google Meet transcripts. Every proposed change is **citation-grounded** — the model must cite the exact transcript segment(s) that justify each edit. Users approve or deny changes through a diff UI; denials feed back into a RAG loop that improves future runs.

Core loop:
1. Ingest Google Meet transcript via Meet REST API (`conferenceRecords.transcripts.entries`)
2. Match discussion to Jira/Linear tickets via orchestrator LLM tools
3. Draft proposals — each with mandatory `proposal_citations` pointing to real `segment_id`s
4. Surface proposals as a diff + citations panel for team review
5. On approval → apply to Jira/Linear; on denial → store structured feedback (which citations were wrong + reason) → embed → retrieve on next run

## Architecture (v1)

```
Google Workspace OAuth
        |
        v
  Meet REST API (transcript entries: text, speaker, start_ms, end_ms)
        |
        v
  Run record created → transcript_segments persisted (immutable, stable segment_id)
        |
        v
  Orchestrator (LLM + tools)
    ├── Jira REST: search, read issues
    ├── Linear GraphQL: search, read issues
    └── RAG retrieval: prior feedback_events for this workspace
        |
        v
  Proposals (with proposal_citations → segment_ids)
        |
        v
  Review UI: diff hunk + citations panel (click → transcript highlight)
    ├── Approve → write to Jira/Linear
    └── Deny → feedback_event (reason + disputed_segment_ids) → pgvector embed
                    |
                    └── retrieved on next run to prevent repeated mistakes
```

## Data Model

| Table | Key fields | Purpose |
|-------|-----------|---------|
| `runs` | `id`, `conference_record_id`, `status`, `created_at` | One row per meeting session |
| `transcript_segments` | `run_id`, `segment_id`, `start_ms`, `end_ms`, `speaker_ref`, `text` | Immutable grounding units |
| `proposals` | `run_id`, `target` (jira/linear), `operation` (create/update), `before`, `after`, `status` | Proposed ticket changes |
| `proposal_citations` | `proposal_id`, `segment_ids[]`, `quote`, `rationale` | Evidence linking proposal → transcript |
| `feedback_events` | `proposal_id`, `reason`, `taxonomy`, `disputed_segment_ids[]` | Structured denial feedback for RAG |

**Status values for proposals**: `pending → approved / denied → applied / failed`

**Feedback taxonomy**: `wrong_issue`, `wrong_field`, `transcript_misread`, `missing_context`, `policy`

## Tech Stack

- **Language**: Python 3.11+
- **API framework**: FastAPI
- **Database**: Postgres + pgvector (for feedback embeddings)
- **LLM**: Claude via Anthropic SDK
- **Meeting source**: Google Meet REST API (primary); paste endpoint as fallback
- **PM integrations (v1)**: Jira REST API, Linear GraphQL API
- **Auth**: Google Workspace OAuth (scopes: Meet, optionally Drive/Docs)
- **Frontend**: TBD (diff + citations UI)
- **Infrastructure**: docker-compose (backend + postgres)

## Project Structure (Planned)

```
PM agent/
├── .claude/
│   ├── CLAUDE.md           # Claude Code entry point (auto-loaded)
│   └── AGENTS.md           # Full project context (imported by CLAUDE.md)
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── core/           # Orchestrator, proposal engine, citations validator
│   │   ├── ingest/         # Meet API client, transcript parser, segment storage
│   │   ├── integrations/
│   │   │   ├── jira.py     # Jira REST client (search/read/write)
│   │   │   └── linear.py   # Linear GraphQL client (search/read/write)
│   │   ├── rag/            # Feedback embedding, retrieval, pgvector
│   │   ├── models/         # SQLAlchemy models
│   │   └── config.py       # Settings, env vars, OAuth config
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # Review UI (diff + citations panel)
├── docker-compose.yml
└── README.md
```

## FastAPI Endpoints (v1)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/runs/from-meet` | Ingest transcript from `conference_record_id` |
| `POST` | `/runs` | Ingest pasted transcript (fallback) |
| `GET` | `/runs/{id}/proposals` | List proposals with citations |
| `POST` | `/runs/{id}/proposals/{pid}/approve` | Approve + apply to PM tool |
| `POST` | `/runs/{id}/proposals/{pid}/deny` | Deny with `{ reason, disputed_segment_ids[] }` |

## Orchestrator Contract

1. **No writes without citations** — every proposal must include at least one `proposal_citation` with a real `segment_id`. Validate in code; reject tool output that cites non-existent segments.
2. **No apply without approval** — PM tool writes only after explicit user approval.
3. **Retrieve before drafting** — pull prior `feedback_events` via pgvector on each run so past mistakes are in context.

## Phased Delivery

| Phase | Goal |
|-------|------|
| A | DB schema + Run + segment ingestion (Meet API or paste) + transcript viewer |
| B | Jira + Linear read/search + proposal generation with mandatory citations + diff UI |
| C | Approve/deny → apply; denial feedback → embeddings → retrieval on next run |
| D | Batch approve, stronger field handling, observability |

## Development Conventions

- `async/await` for all I/O (API calls, DB queries)
- Type-annotate all function signatures
- No silent failures in the proposal/apply pipeline — surface errors explicitly
- Tests mirror `backend/app/` structure under `backend/tests/`
- Never hardcode credentials — use `.env` via `pydantic-settings`
- Google OAuth scopes and Meet API setup must be documented for contributors

## Open Decisions (TBD)

- Frontend framework (React, SvelteKit, or server-rendered)
- Embedding model for feedback RAG (OpenAI, Cohere, or local)
- Whether to support Google Docs transcript fallback in MVP
- Deployment target (Railway, Fly.io, GCP)
