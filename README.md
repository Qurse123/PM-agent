# PM Agent

An AI-powered meeting agent that keeps Jira and Linear tickets up to date using Google Meet transcripts. Every proposed ticket change is **citation-grounded** — the model cites the exact transcript segments that justify each edit. Your team reviews a diff before anything is written.

## How It Works

1. **Ingest** — connect a Google Meet `conference_record_id`; the agent fetches the transcript via the Meet REST API and stores immutable segments (text, speaker, timestamps)
2. **Identify** — the orchestrator searches Jira and Linear to find tickets related to the discussion
3. **Propose** — the LLM drafts ticket changes; every change must cite real transcript segments (validated in code)
4. **Review** — your team sees a diff UI with a citations panel; clicking a citation jumps to the transcript moment that justified the change
5. **Apply or deny** — approve to write to Jira/Linear; deny with a reason and mark which citations were wrong
6. **Learn** — denials are embedded and retrieved on future runs so the model doesn't repeat the same mistakes

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

## Contributing

See [AGENTS.md](AGENTS.md) for the full architecture, data model, orchestrator contract, and development conventions.
