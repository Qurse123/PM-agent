"""
Tests for the proposals API (app/api/proposals.py).

Tests:
  1. GET /runs/{run_id}/proposals returns 404 when run not found
  2. GET /runs/{run_id}/proposals returns empty list when no proposals
  3. GET /runs/{run_id}/proposals returns proposals with citations
  4. POST /runs/{run_id}/analyze returns 404 when run not found
  5. POST /runs/{run_id}/analyze returns 409 when run not in 'ready' status
  6. POST /runs/{run_id}/analyze returns 202 and enqueues job
  7. POST approve returns 404 when proposal not found
  8. POST approve returns 409 when proposal not pending
  9. POST approve sets status to 'approved'
  10. POST deny sets status to 'denied'
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.db import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(status: str = "ready") -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.conference_record_id = "conf-test"
    run.status = status
    run.created_at = datetime.now(timezone.utc)
    return run


def _make_proposal(run_id: uuid.UUID, status: str = "pending") -> MagicMock:
    proposal = MagicMock()
    proposal.id = uuid.uuid4()
    proposal.run_id = run_id
    proposal.target = "linear"
    proposal.operation = "create"
    proposal.before = None
    proposal.after = {"title": "New ticket"}
    proposal.status = status
    proposal.created_at = datetime.now(timezone.utc)
    proposal.citations = []
    return proposal


def _make_db(execute_side_effects: list) -> AsyncMock:
    """Build a mock AsyncSession with a sequence of execute() results."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=execute_side_effects)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _scalar_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values: list) -> MagicMock:
    scalars = MagicMock()
    scalars.all.return_value = values
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


def _mock_arq_pool() -> AsyncMock:
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    return pool


# ---------------------------------------------------------------------------
# 1. GET /proposals returns 404 when run not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_proposals_run_not_found():
    db = _make_db([_scalar_result(None)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/runs/{uuid.uuid4()}/proposals")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. GET /proposals returns empty list when no proposals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_proposals_empty():
    run = _make_run()
    db = _make_db([_scalar_result(run), _scalars_result([])])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/runs/{run.id}/proposals")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. GET /proposals returns proposals with citations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_proposals_with_citations():
    run = _make_run()
    proposal = _make_proposal(run.id)

    citation = MagicMock()
    citation.id = uuid.uuid4()
    citation.segment_ids = ["seg-0001"]
    citation.quote = "We need to ship this."
    citation.rationale = "Explicit deadline."
    proposal.citations = [citation]

    db = _make_db([_scalar_result(run), _scalars_result([proposal])])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/runs/{run.id}/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["target"] == "linear"
        assert len(data[0]["citations"]) == 1
        assert data[0]["citations"][0]["quote"] == "We need to ship this."
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. POST /analyze returns 404 when run not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_run_not_found():
    db = _make_db([_scalar_result(None)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{uuid.uuid4()}/analyze")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. POST /analyze returns 409 when run not in 'ready' status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_run_wrong_status():
    run = _make_run(status="analyzing")
    db = _make_db([_scalar_result(run)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{run.id}/analyze")
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. POST /analyze returns 202 and enqueues job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_enqueues_job():
    run = _make_run(status="ready")
    db = _make_db([_scalar_result(run)])
    arq_pool = _mock_arq_pool()

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = arq_pool
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{run.id}/analyze")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"
        assert data["run_id"] == str(run.id)
        arq_pool.enqueue_job.assert_called_once_with("orchestrate_run", str(run.id))
        assert run.status == "analyzing"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. POST approve returns 404 when proposal not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_proposal_not_found():
    run_id = uuid.uuid4()
    db = _make_db([_scalar_result(None)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{run_id}/proposals/{uuid.uuid4()}/approve")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. POST approve returns 409 when proposal not pending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_proposal_not_pending():
    run = _make_run()
    proposal = _make_proposal(run.id, status="approved")
    db = _make_db([_scalar_result(proposal)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{run.id}/proposals/{proposal.id}/approve")
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. POST approve sets status to 'approved'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_proposal_success():
    run = _make_run()
    proposal = _make_proposal(run.id, status="pending")
    db = _make_db([_scalar_result(proposal)])

    async def _refresh(obj):
        pass  # status already mutated in-place

    db.refresh = AsyncMock(side_effect=_refresh)

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{run.id}/proposals/{proposal.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert proposal.status == "approved"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 10. POST deny sets status to 'denied'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deny_proposal_success():
    run = _make_run()
    proposal = _make_proposal(run.id, status="pending")
    db = _make_db([_scalar_result(proposal)])

    async def _refresh(obj):
        pass

    db.refresh = AsyncMock(side_effect=_refresh)

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/runs/{run.id}/proposals/{proposal.id}/deny")
        assert resp.status_code == 200
        assert resp.json()["status"] == "denied"
        assert proposal.status == "denied"
    finally:
        app.dependency_overrides.clear()
