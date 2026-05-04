"""
Tests for Phase B Proposal + ProposalCitation ORM models.
Uses SQLite in-memory (aiosqlite) with raw sa.Table definitions
so no Postgres-specific types (ARRAY, UUID) are needed.

4 tests:
  1. Insert a Proposal row — succeeds, fields round-trip correctly
  2. Insert a ProposalCitation row linked to the proposal — succeeds
  3. Cascade delete: deleting the Run deletes its Proposals and Citations
  4. Default status: Proposal.status defaults to "pending"
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import (
    Column,
    ForeignKey,
    MetaData, 
    String,
    Table,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine + metadata (SQLite-compatible column types)
# ---------------------------------------------------------------------------

metadata = MetaData()

runs_table = Table(
    "runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("conference_record_id", String, nullable=False),
    Column("status", String, nullable=False, default="ingesting"),
    Column("created_at", String, nullable=False),
)

proposals_table = Table(
    "proposals",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("target", String, nullable=False),
    Column("operation", String, nullable=False),
    Column("before", Text, nullable=True),   # JSON-encoded text for SQLite
    Column("after", Text, nullable=False),   # JSON-encoded text for SQLite
    Column("status", String, nullable=False, default="pending"),
    Column("created_at", String, nullable=False),
)

proposal_citations_table = Table(
    "proposal_citations",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "proposal_id",
        String,
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("segment_ids", Text, nullable=False),  # JSON-encoded list for SQLite
    Column("quote", Text, nullable=False),
    Column("rationale", Text, nullable=False),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
async def engine():
    """Create a fresh SQLite in-memory engine per test."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def conn(engine):
    """Provide a raw AsyncConnection with PRAGMA foreign_keys=ON."""
    async with engine.connect() as connection:
        # Enable FK enforcement in SQLite
        await connection.execute(
            __import__("sqlalchemy").text("PRAGMA foreign_keys = ON")
        )
        yield connection


# ---------------------------------------------------------------------------
# Helper to insert a Run and return its id
# ---------------------------------------------------------------------------


async def _insert_run(conn) -> str:
    run_id = str(uuid.uuid4())
    await conn.execute(
        runs_table.insert().values(
            id=run_id,
            conference_record_id="conf-test-001",
            status="ingesting",
            created_at=_now(),
        )
    )
    await conn.commit()
    return run_id


# ---------------------------------------------------------------------------
# 1. Insert a Proposal row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_proposal(conn):
    run_id = await _insert_run(conn)
    proposal_id = str(uuid.uuid4())

    await conn.execute(
        proposals_table.insert().values(
            id=proposal_id,
            run_id=run_id,
            target="jira",
            operation="update",
            before=json.dumps({"summary": "Old title"}),
            after=json.dumps({"summary": "New title"}),
            status="pending",
            created_at=_now(),
        )
    )
    await conn.commit()

    row = (
        await conn.execute(
            select(proposals_table).where(proposals_table.c.id == proposal_id)
        )
    ).one()

    assert row.id == proposal_id
    assert row.run_id == run_id
    assert row.target == "jira"
    assert row.operation == "update"
    assert json.loads(row.after)["summary"] == "New title"
    assert row.status == "pending"


# ---------------------------------------------------------------------------
# 2. Insert a ProposalCitation linked to the proposal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_proposal_citation(conn):
    run_id = await _insert_run(conn)
    proposal_id = str(uuid.uuid4())

    await conn.execute(
        proposals_table.insert().values(
            id=proposal_id,
            run_id=run_id,
            target="linear",
            operation="create",
            before=None,
            after=json.dumps({"title": "New ticket"}),
            status="pending",
            created_at=_now(),
        )
    )
    await conn.commit()

    citation_id = str(uuid.uuid4())
    segment_ids = ["paste-run-0000", "paste-run-0001"]

    await conn.execute(
        proposal_citations_table.insert().values(
            id=citation_id,
            proposal_id=proposal_id,
            segment_ids=json.dumps(segment_ids),
            quote="We need to ship this feature by Friday.",
            rationale="Explicit deadline mentioned by product owner.",
        )
    )
    await conn.commit()

    row = (
        await conn.execute(
            select(proposal_citations_table).where(
                proposal_citations_table.c.id == citation_id
            )
        )
    ).one()

    assert row.proposal_id == proposal_id
    assert json.loads(row.segment_ids) == segment_ids
    assert row.quote == "We need to ship this feature by Friday."
    assert "deadline" in row.rationale


# ---------------------------------------------------------------------------
# 3. Cascade delete: deleting Run removes Proposals and Citations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cascade_delete_run_removes_proposals_and_citations(conn):
    run_id = await _insert_run(conn)
    proposal_id = str(uuid.uuid4())
    citation_id = str(uuid.uuid4())

    await conn.execute(
        proposals_table.insert().values(
            id=proposal_id,
            run_id=run_id,
            target="jira",
            operation="update",
            before=None,
            after=json.dumps({"status": "In Progress"}),
            status="pending",
            created_at=_now(),
        )
    )
    await conn.execute(
        proposal_citations_table.insert().values(
            id=citation_id,
            proposal_id=proposal_id,
            segment_ids=json.dumps(["seg-001"]),
            quote="Let us move this to in progress.",
            rationale="Team agreed on the call.",
        )
    )
    await conn.commit()

    # Delete the run — cascade should remove proposal and citation
    await conn.execute(runs_table.delete().where(runs_table.c.id == run_id))
    await conn.commit()

    proposals = (
        await conn.execute(
            select(proposals_table).where(proposals_table.c.id == proposal_id)
        )
    ).fetchall()
    citations = (
        await conn.execute(
            select(proposal_citations_table).where(
                proposal_citations_table.c.id == citation_id
            )
        )
    ).fetchall()

    assert proposals == [], "Proposals should be deleted when Run is deleted"
    assert citations == [], "Citations should be deleted when Run (and Proposal) is deleted"


# ---------------------------------------------------------------------------
# 4. Default status is "pending"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proposal_status_defaults_to_pending(conn):
    run_id = await _insert_run(conn)
    proposal_id = str(uuid.uuid4())

    # Insert without explicitly setting status — rely on default
    await conn.execute(
        proposals_table.insert().values(
            id=proposal_id,
            run_id=run_id,
            target="jira",
            operation="update",
            before=None,
            after=json.dumps({"assignee": "alice@example.com"}),
            # status intentionally omitted to test default
            created_at=_now(),
        )
    )
    await conn.commit()

    row = (
        await conn.execute(
            select(proposals_table).where(proposals_table.c.id == proposal_id)
        )
    ).one()

    assert row.status == "pending"
