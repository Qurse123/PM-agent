"""
Integration tests that require a real Postgres + pgvector database.

Skipped automatically when DATABASE_URL does not point to Postgres.

Covers the things that SQLite-based tests cannot:
  - UUID primary keys (PostgreSQL UUID type)
  - ARRAY(String) columns (segment_ids, disputed_segment_ids)
  - CASCADE deletes across the full FK chain
  - pgvector Vector(1536) column storage and <=> similarity query
  - UniqueConstraint on (run_id, segment_id)
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.db import (
    FeedbackEvent,
    Proposal,
    ProposalCitation,
    Run,
    TranscriptSegment,
)

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    "postgresql" not in DATABASE_URL,
    reason="Integration tests require a real Postgres database (set DATABASE_URL)",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def pg_engine():
    # NullPool: every session.begin() gets a fresh physical connection so
    # cleanup and test sessions never share a connection (asyncpg rejects that).
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(pg_engine) -> AsyncSession:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def cleanup(pg_engine):
    """Delete all runs after each test — cascades to all child tables."""
    yield
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text("DELETE FROM runs"))
        await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(**kwargs) -> Run:
    return Run(
        conference_record_id=kwargs.get("conference_record_id", f"conf-{uuid.uuid4()}"),
        title=kwargs.get("title", "Test meeting"),
        status=kwargs.get("status", "ready"),
    )


def _segment(run_id: uuid.UUID, segment_id: str = "seg-1") -> TranscriptSegment:
    return TranscriptSegment(
        run_id=run_id,
        segment_id=segment_id,
        start_ms=0,
        end_ms=5000,
        speaker_ref="speaker/1",
        text="We should close this sprint.",
    )


def _proposal(run_id: uuid.UUID) -> Proposal:
    return Proposal(
        run_id=run_id,
        target="linear",
        operation="update",
        before={"status": "backlog"},
        after={"status": "in_progress", "title": "Add rate limiting"},
        status="pending",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_uuid_roundtrip(db: AsyncSession):
    """UUID primary key is stored and retrieved correctly."""
    run = _run()
    db.add(run)
    await db.commit()

    fetched = await db.get(Run, run.id)
    assert fetched is not None
    assert isinstance(fetched.id, uuid.UUID)
    assert fetched.title == "Test meeting"
    assert fetched.status == "ready"


@pytest.mark.asyncio
async def test_transcript_segment_unique_constraint(db: AsyncSession):
    """Duplicate (run_id, segment_id) raises IntegrityError."""
    run = _run()
    db.add(run)
    await db.commit()

    db.add(_segment(run.id, "seg-1"))
    await db.commit()

    db.add(_segment(run.id, "seg-1"))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_proposal_citation_array_column(db: AsyncSession):
    """ARRAY(String) on ProposalCitation stores and retrieves correctly."""
    run = _run()
    db.add(run)
    await db.flush()  # assigns run.id before children reference it
    proposal = _proposal(run.id)
    db.add(proposal)
    await db.commit()

    citation = ProposalCitation(
        proposal_id=proposal.id,
        segment_ids=["seg-1", "seg-2", "seg-3"],
        quote="We should close this sprint.",
        rationale="Team agreed to prioritize rate limiting.",
    )
    db.add(citation)
    await db.commit()

    fetched = await db.get(ProposalCitation, citation.id)
    assert fetched is not None
    assert fetched.segment_ids == ["seg-1", "seg-2", "seg-3"]


@pytest.mark.asyncio
async def test_cascade_delete_run_removes_all_children(db: AsyncSession):
    """Deleting a Run cascades to segments, proposals, citations, and feedback."""
    run = _run()
    db.add(run)
    await db.flush()
    proposal = _proposal(run.id)
    db.add(proposal)
    seg = _segment(run.id)
    db.add(seg)
    await db.commit()

    citation = ProposalCitation(
        proposal_id=proposal.id,
        segment_ids=["seg-1"],
        quote="test quote",
        rationale="test rationale",
    )
    feedback = FeedbackEvent(
        proposal_id=proposal.id,
        reason="wrong issue",
        category="wrong_issue",
        disputed_segment_ids=["seg-1"],
        embedding=None,
    )
    db.add(citation)
    db.add(feedback)
    await db.commit()

    seg_id, proposal_id, citation_id, feedback_id = (
        seg.id, proposal.id, citation.id, feedback.id,
    )

    await db.delete(run)
    await db.commit()
    db.expunge_all()  # clear identity map so gets hit the DB

    assert await db.get(TranscriptSegment, seg_id) is None
    assert await db.get(Proposal, proposal_id) is None
    assert await db.get(ProposalCitation, citation_id) is None
    assert await db.get(FeedbackEvent, feedback_id) is None


@pytest.mark.asyncio
async def test_pgvector_storage_and_similarity_query(db: AsyncSession):
    """Vector(1536) stores correctly and <=> returns nearest neighbour first."""
    run = _run()
    db.add(run)
    await db.flush()
    proposal = _proposal(run.id)
    db.add(proposal)
    await db.commit()

    vec_a = [1.0] + [0.0] * 1535
    vec_b = [0.0, 1.0] + [0.0] * 1534

    fe_a = FeedbackEvent(
        proposal_id=proposal.id,
        reason="wrong issue — A",
        category="wrong_issue",
        disputed_segment_ids=["seg-1"],
        embedding=vec_a,
    )
    fe_b = FeedbackEvent(
        proposal_id=proposal.id,
        reason="wrong field — B",
        category="wrong_field",
        disputed_segment_ids=["seg-2"],
        embedding=vec_b,
    )
    db.add(fe_a)
    db.add(fe_b)
    await db.commit()

    query_vec = "[" + ",".join(str(v) for v in vec_a) + "]"
    result = await db.execute(
        text(
            "SELECT id FROM feedback_events "
            "WHERE embedding IS NOT NULL "
            "ORDER BY embedding <=> CAST(:vec AS vector) "
            "LIMIT 2"
        ).bindparams(vec=query_vec)
    )
    rows = result.fetchall()
    assert len(rows) == 2
    assert rows[0][0] == fe_a.id


@pytest.mark.asyncio
async def test_feedback_event_disputed_segment_ids_array(db: AsyncSession):
    """ARRAY(String) on FeedbackEvent.disputed_segment_ids round-trips correctly."""
    run = _run()
    db.add(run)
    await db.flush()
    proposal = _proposal(run.id)
    db.add(proposal)
    await db.commit()

    fe = FeedbackEvent(
        proposal_id=proposal.id,
        reason="Transcript was misread",
        category="transcript_misread",
        disputed_segment_ids=["seg-10", "seg-11", "seg-12"],
        embedding=None,
    )
    db.add(fe)
    await db.commit()

    fetched = await db.get(FeedbackEvent, fe.id)
    assert fetched is not None
    assert fetched.disputed_segment_ids == ["seg-10", "seg-11", "seg-12"]
