# Contributing to PM Agent

Thanks for your interest in contributing. This document covers how to get set up and what we expect from pull requests.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Postgres + Redis)
- An OpenAI API key
- A Linear API key (for testing proposal generation end-to-end)

## Setup

```bash
git clone https://github.com/Qurse123/PM-agent.git
cd PM-agent
cp backend/.env.example backend/.env  # fill in your keys
docker compose up -d
cd backend && alembic upgrade head
uvicorn app.main:app --reload         # API at :8000
python run_worker.py                  # background worker (separate terminal)
cd frontend && npm install && npm run dev  # UI at :5173
```

## Development Conventions

- `async/await` for all I/O — no blocking calls in the API or worker
- Type-annotate all function signatures
- Never hardcode credentials — use `.env` via `pydantic-settings`
- **Citation contract is load-bearing**: every proposal must reference real `segment_id`s from the current run — this is enforced in code, not just convention
- Before adding a new module, check if `backend/app/core/` or `backend/app/integrations/` can be extended instead
- Run `pytest backend/tests/ -v` before submitting

## Running Tests

```bash
cd backend

# Unit tests
pytest tests/ -v

# Integration tests (requires Postgres running)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pm_agent \
  pytest tests/test_integration_postgres.py -v
```

## Pull Requests

- Fork the repo and work on a feature branch — no direct pushes to `main`
- Keep PRs focused; one logical change per PR
- Describe what changed and why in the PR description
- All CI checks must pass before merge (lint, type check, tests, frontend build)
- If your change touches the data model, run `alembic revision --autogenerate` and include the migration
