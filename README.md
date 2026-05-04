# PM Agent

An agentic AI system that turns meeting transcripts into Linear ticket updates — automatically. Upload a transcript and an LLM agent searches your Linear board, reasons over the discussion, and proposes field changes, status moves, and new issues. Every proposal is **citation-grounded**: the agent must cite the exact transcript segments that justify each edit, enforced in code.

Before drafting proposals, the agent runs a **RAG retrieval step** — querying a pgvector database of past denial feedback so it learns from mistakes across runs. Your team reviews everything in a kanban diff UI before anything is written.

## How It Works

1. **Upload** — drop a `.txt`, `.vtt`, or `.srt` transcript file; supports batch upload (one run per file)
2. **RAG retrieval** — the agent queries a pgvector vector database for similar past feedback before drafting anything
3. **Agent loop** — the LLM searches Linear, reads relevant tickets, and proposes changes grounded in transcript citations
4. **Review** — a 3-column kanban (Processing → To Review → Reviewed) shows each run; proposals display a field diff alongside the transcript excerpts that back them up
5. **Approve or deny** — approvals write to Linear; denials capture which citations were wrong and embed the feedback into the vector DB
6. **Learn** — denial embeddings are retrieved on future runs so the agent improves without retraining

## Architecture

```
Google Workspace OAuth
        |
        v
  Meet REST API  →  transcript_segments (immutable, stable segment_id)
        |
        v
  Orchestrator (Claude + tools)
    ├── Jira REST search/read
    ├── Linear GraphQL search/read
    └── RAG: prior feedback_events via pgvector
        |
        v
  Proposals + proposal_citations (segment_id refs + quote + rationale)
        |
        v
  Diff UI + citations panel
    ├── Approve → write to Jira / Linear
    └── Deny   → feedback_event (reason + disputed_segment_ids) → embed → retrieve next run
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| API | FastAPI (Python 3.11+) |
| Database | Postgres + pgvector |
| LLM | Claude (Anthropic SDK) |
| Meeting source | Google Meet REST API |
| PM integrations | Jira REST, Linear GraphQL |
| Auth | Google Workspace OAuth |
| Infrastructure | docker-compose |

## Project Structure

```
PM agent/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (runs, proposals)
│   │   ├── core/           # Orchestrator, proposal engine, citations validator
│   │   ├── ingest/         # Meet API client, segment storage
│   │   ├── integrations/   # jira.py, linear.py
│   │   ├── rag/            # Feedback embeddings, pgvector retrieval
│   │   ├── models/         # SQLAlchemy models
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # Diff + citations review UI
├── docker-compose.yml
├── AGENTS.md               # Full project context for coding agents
└── CLAUDE.md               # Claude Code entry point (imports AGENTS.md)
```

## Getting Started

**Prerequisites:** Docker, Node.js 20+, Python 3.11+

```bash
# 1. Clone and configure
git clone https://github.com/your-org/pm-agent.git
cd pm-agent
cp backend/.env.example backend/.env   # fill in API keys

# 2. Start Postgres + Redis
docker compose up -d

# 3. Run database migrations
cd backend && alembic upgrade head

# 4. Start the API server
uvicorn app.main:app --reload

# 5. Start the background worker (separate terminal)
python run_worker.py

# 6. Start the frontend (separate terminal)
cd frontend && npm install && npm run dev
```

The review UI is at `http://localhost:5173` and the API at `http://localhost:8000`.

## Running Tests

```bash
cd backend

# Unit tests (no external dependencies)
pytest tests/ -v

# Integration tests (requires Postgres + pgvector running)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pm_agent \
  pytest tests/test_integration_postgres.py -v
```

CI runs both automatically — the integration tests are skipped if `DATABASE_URL` doesn't point to Postgres.

## Releases

Releases are automated via GitHub Actions. When a `v*` tag is pushed, CI runs the full test suite and a GitHub Release is created with an auto-generated changelog.

```bash
git tag v0.1.0
git push origin v0.1.0
```

Use [semantic versioning](https://semver.org). The release workflow requires all CI jobs to pass before publishing. See the [Releases page](../../releases) for the full history.

## Contributing

See [AGENTS.md](AGENTS.md) for the full architecture, data model, orchestrator contract, and development conventions.
