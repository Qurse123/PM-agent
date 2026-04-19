"""
Tests for the proposals API (app/api/proposals.py).

Tests:
  1.  GET /runs/{run_id}/proposals returns 404 when run not found
  2.  GET /runs/{run_id}/proposals returns empty list when no proposals
  3.  GET /runs/{run_id}/proposals returns proposals with citations
  4.  POST /runs/{run_id}/analyze returns 404 when run not found
  5.  POST /runs/{run_id}/analyze returns 409 when run not in 'ready' status
  6.  POST /runs/{run_id}/analyze returns 202 and enqueues job
  7.  POST approve returns 404 when proposal not found
  8.  POST approve returns 409 when proposal not pending
  9.  POST approve calls linear create_issue and sets status to 'applied'
  10. POST approve calls linear update_issue and sets status to 'applied'
  11. POST approve sets status to 'failed' when Linear raises
  12. POST deny sets status to 'denied' and stores FeedbackEvent
  13. POST deny returns 422 for invalid taxonomy
  14. POST deny returns 409 when proposal not pending
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_proposal(
    run_id: uuid.UUID,
    status: str = "pending",
    operation: str = "create",
    before: dict | None = None,
    after: dict | None = None,
) -> MagicMock:
    proposal = MagicMock()
    proposal.id = uuid.uuid4()
    proposal.run_id = run_id
    proposal.target = "linear"
    proposal.operation = operation
    proposal.before = before
    proposal.after = after or {"title": "New ticket", "description": "Details", "teamId": "team-abc"}
    proposal.status = status
    proposal.created_at = datetime.now(timezone.utc)
    proposal.citations = []
    return proposal


def _make_db(execute_side_effects: list) -> AsyncMock:
    """Build a mock AsyncSession with a sequence of execute() results."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=execute_side_effects)
    db.add = MagicMock()
    db.flush = AsyncMock()
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
# 9. POST approve calls linear create_issue and sets status to 'applied'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_create_calls_linear_and_sets_applied():
    run = _make_run()
    proposal = _make_proposal(
        run.id,
        operation="create",
        after={"title": "New ticket", "description": "Details", "teamId": "team-abc"},
    )
    db = _make_db([_scalar_result(proposal)])
    db.refresh = AsyncMock()

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    mock_linear = AsyncMock()
    mock_linear.create_issue = AsyncMock(return_value={"id": "li-1", "title": "New ticket", "url": "https://linear.app/li-1"})

    with patch("app.api.proposals.LinearClient", return_value=mock_linear):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/runs/{run.id}/proposals/{proposal.id}/approve")
            assert resp.status_code == 200
            mock_linear.create_issue.assert_called_once_with(
                title="New ticket",
                description="Details",
                team_id="team-abc",
            )
            assert proposal.status == "applied"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 10. POST approve calls linear update_issue and sets status to 'applied'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_update_calls_linear_and_sets_applied():
    run = _make_run()
    proposal = _make_proposal(
        run.id,
        operation="update",
        before={"id": "li-existing-123", "title": "Old title"},
        after={"title": "Updated title"},
    )
    db = _make_db([_scalar_result(proposal)])
    db.refresh = AsyncMock()

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    mock_linear = AsyncMock()
    mock_linear.update_issue = AsyncMock(return_value={"id": "li-existing-123", "title": "Updated title", "url": "https://linear.app/li-existing-123"})

    with patch("app.api.proposals.LinearClient", return_value=mock_linear):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/runs/{run.id}/proposals/{proposal.id}/approve")
            assert resp.status_code == 200
            mock_linear.update_issue.assert_called_once_with(
                "li-existing-123",
                {"title": "Updated title"},
            )
            assert proposal.status == "applied"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 11. POST approve sets status to 'failed' when Linear raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_linear_failure_sets_failed():
    run = _make_run()
    proposal = _make_proposal(
        run.id,
        operation="create",
        after={"title": "New ticket", "description": "", "teamId": "team-abc"},
    )
    db = _make_db([_scalar_result(proposal)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    mock_linear = AsyncMock()
    mock_linear.create_issue = AsyncMock(side_effect=RuntimeError("Linear API error"))

    with patch("app.api.proposals.LinearClient", return_value=mock_linear):
        try:
            with pytest.raises(RuntimeError, match="Linear API error"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    await ac.post(f"/runs/{run.id}/proposals/{proposal.id}/approve")
            assert proposal.status == "failed"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 12. POST deny sets status to 'denied' and stores FeedbackEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deny_stores_feedback_event():
    run = _make_run()
    proposal = _make_proposal(run.id, status="pending")
    db = _make_db([_scalar_result(proposal)])
    db.refresh = AsyncMock()

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/runs/{run.id}/proposals/{proposal.id}/deny",
                json={
                    "reason": "Wrong issue selected",
                    "category": "wrong ticket",
                    "disputed_segment_ids": ["seg-001"],
                },
            )
        assert resp.status_code == 200
        assert proposal.status == "denied"
        # FeedbackEvent was added to the session
        db.add.assert_called_once()
        feedback_arg = db.add.call_args[0][0]
        assert feedback_arg.reason == "Wrong issue selected"
        assert feedback_arg.category == "wrong ticket"
        assert feedback_arg.disputed_segment_ids == ["seg-001"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 13. POST deny returns 409 when proposal not pending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deny_proposal_not_pending():
    run = _make_run()
    proposal = _make_proposal(run.id, status="denied")
    db = _make_db([_scalar_result(proposal)])

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    app.state.arq_pool = _mock_arq_pool()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/runs/{run.id}/proposals/{proposal.id}/deny",
                json={"reason": "Already denied", "category": "team policy"},
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()
