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
Transcript file upload (.txt / .vtt / .srt)
        |
        v
  transcript_segments (immutable, stable segment_id)
        |
        v
  RAG retrieval → pgvector similarity search over past feedback_events
        |
        v
  Orchestrator (OpenAI + tools)
    ├── Linear GraphQL search/read
    └── Citation validator (segment_ids must exist — enforced in code)
        |
        v
  Proposals + proposal_citations (segment_id refs + quote + rationale)
        |
        v
  Kanban review UI (Processing → To Review → Reviewed)
    ├── Approve → write to Linear
    └── Deny   → feedback_event (reason + disputed_segment_ids) → embed → pgvector
                    |
                    └── retrieved on next run by RAG step
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| API | FastAPI (Python 3.11+) |
| Database | Postgres + pgvector |
| LLM | OpenAI |
| Transcript source | File upload (.txt, .vtt, .srt) |
| PM integrations | Linear GraphQL |
| Queue | Redis + arq |
| Infrastructure | docker-compose |

## Project Structure

```
PM agent/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (runs, proposals)
│   │   ├── core/           # Orchestrator, proposal engine, citations validator
│   │   ├── ingest/         # Transcript parser, segment storage
│   │   ├── integrations/   # linear.py (Linear GraphQL client)
│   │   ├── rag/            # Feedback embeddings, pgvector retrieval
│   │   ├── models/         # SQLAlchemy models
│   │   └── config.py
│   ├── Dockerfile
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React + Vite diff + citations review UI (always run locally)
├── docker-compose.yml
├── AGENTS.md               # Full project context for coding agents
└── CLAUDE.md               # Claude Code entry point (imports AGENTS.md)
```

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes `docker compose`)
- Node.js 20+ (for the frontend — not Dockerized)
- Python 3.11+ (only needed for the **Local Dev** path below)

### API Keys

You need two keys before running anything:

- **OpenAI API key** — [platform.openai.com](https://platform.openai.com) → API keys → Create new secret key
- **Linear API key** — Linear app → Settings → API → Personal API keys → Create key

Copy the example env file and fill in both keys:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set openai_api_key and linear_api_key at minimum
```

---

### Option A — Fully Docker (recommended)

All backend services (Postgres, Redis, API server, background worker) run as Docker containers. The frontend is always run locally.

```bash
# 1. Clone
git clone https://github.com/Qurse123/PM-agent.git
cd pm-agent

# 2. Configure env
cp backend/.env.example backend/.env
# Fill in openai_api_key and linear_api_key in backend/.env

# 3. Start all backend services
docker compose up -d

# 4. Run database migrations (inside the backend container)
docker compose exec backend alembic upgrade head

# 5. Start the frontend (separate terminal — not Dockerized)
cd frontend && npm install && npm run dev
```

The review UI is at `http://localhost:5173` and the API at `http://localhost:8000`.

To stop everything: `docker compose down`

---

### Option B — Local Dev (backend runs on host)

Use this if you want to run the API server and worker directly on your machine (e.g. for faster iteration with a debugger attached). Only Postgres and Redis run in Docker.

```bash
# 1. Clone
git clone https://github.com/Qurse123/PM-agent.git
cd pm-agent

# 2. Configure env
cp backend/.env.example backend/.env
# Fill in openai_api_key and linear_api_key in backend/.env

# 3. Start only Postgres and Redis
docker compose up -d postgres redis

# 4. Set up Python environment
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 5. Run database migrations
alembic upgrade head

# 6. Start the API server
uvicorn app.main:app --reload

# 7. Start the background worker (separate terminal, venv active)
cd backend && python run_worker.py

# 8. Start the frontend (separate terminal, from project root)
cd frontend && npm install && npm run dev
```

The review UI is at `http://localhost:5173` and the API at `http://localhost:8000`.

> **Note:** When running locally, `DATABASE_URL` and `REDIS_URL` in `.env` use `localhost`. The Docker-only path overrides these to use Docker service names — don't mix the two.

---

## Running Tests

```bash
cd backend

# Activate venv if using local dev path
source venv/bin/activate

# Unit tests (no external dependencies)
pytest tests/ -v

# Integration tests (requires Postgres + pgvector running)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pm_agent \
  pytest tests/test_integration_postgres.py -v
```

When running in Docker, you can also run tests inside the container:

```bash
docker compose exec backend pytest tests/ -v
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
