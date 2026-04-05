@AGENTS.md

## Claude Code Notes

- Use **plan mode** before implementing anything that touches the data model, orchestrator contract, or citation validation logic
- Before adding a new file or module, check if an existing one in `backend/app/core/` or `backend/app/integrations/` can be extended
- The **citation contract is load-bearing**: never draft a proposal without `proposal_citations` pointing to real `segment_id`s — this is enforced in code, not just convention
- When working on the RAG pipeline (`backend/app/rag/`), always verify pgvector is available before assuming embedding retrieval works
- Run `pytest backend/tests/` to verify before marking any feature complete

## Key Entry Points (once scaffolded)

- `backend/app/main.py` — FastAPI app init
- `backend/app/core/orchestrator.py` — LLM agent loop
- `backend/app/ingest/meet.py` — Google Meet transcript ingestion
- `backend/app/api/runs.py` — run + proposal endpoints
