"""
Tests for the workspace context API (app/api/workspace.py).

4 tests:
  1. GET /workspace returns 404 when not configured
  2. PUT /workspace creates context and returns 200
  3. PUT /workspace updates existing row (upsert)
  4. GET /workspace returns 200 after configuration
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
# Mock DB helpers
# ---------------------------------------------------------------------------


def _make_workspace_db(workspace=None):
    workspace_result = MagicMock()
    workspace_result.scalar_one_or_none.return_value = workspace

    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=workspace_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _make_workspace_obj(**kwargs):
    ws = MagicMock()
    ws.id = kwargs.get("id", uuid.uuid4())
    ws.context = kwargs.get("context", None)
    ws.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
    return ws


# ---------------------------------------------------------------------------
# 1. GET /workspace returns 404 when not configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workspace_404_when_not_configured():
    mock_db = _make_workspace_db(workspace=None)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/workspace")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Workspace context not configured"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. PUT /workspace creates context and returns 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_workspace_creates_context():
    ws_id = uuid.uuid4()
    mock_db = _make_workspace_db(workspace=None)

    async def _refresh_side_effect(obj):
        obj.id = ws_id
        obj.context = "Backend Platform team. Focus on infra tickets only."
        obj.updated_at = datetime.now(timezone.utc)

    mock_db.refresh = AsyncMock(side_effect=_refresh_side_effect)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                "/workspace",
                json={"context": "Backend Platform team. Focus on infra tickets only."},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["context"] == "Backend Platform team. Focus on infra tickets only."
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. PUT /workspace updates existing row (upsert)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_workspace_updates_existing():
    existing_ws = _make_workspace_obj(context="Old instructions.")
    mock_db = _make_workspace_db(workspace=existing_ws)

    async def _refresh_side_effect(obj):
        obj.context = "New instructions."
        obj.updated_at = datetime.now(timezone.utc)

    mock_db.refresh = AsyncMock(side_effect=_refresh_side_effect)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/workspace", json={"context": "New instructions."})
        assert resp.status_code == 200
        assert resp.json()["context"] == "New instructions."
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. GET /workspace returns 200 when configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workspace_returns_200_when_configured():
    ws = _make_workspace_obj(
        context="Focus on P0 bugs only.",
        updated_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    mock_db = _make_workspace_db(workspace=ws)

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/workspace")
        assert resp.status_code == 200
        assert resp.json()["context"] == "Focus on P0 bugs only."
    finally:
        app.dependency_overrides.clear()
