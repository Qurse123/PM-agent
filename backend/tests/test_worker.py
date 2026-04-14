"""
Tests for the arq worker (app/core/worker.py).

4 tests:
  1. Job calls run_orchestrator when run status is 'analyzing'
  2. Sets run.status = 'ready' on success
  3. Sets run.status = 'failed' on exception (and re-raises)
  4. Skips silently if run not found or status is not 'analyzing'
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.worker import orchestrate_run


def _make_run(status: str = "analyzing") -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.status = status
    return run


def _make_session(run) -> AsyncMock:
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = run

    session = AsyncMock()
    session.execute = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ---------------------------------------------------------------------------
# 1 & 2. Success path: orchestrator called, status set to 'ready'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_calls_orchestrator_and_sets_ready():
    run = _make_run(status="analyzing")
    session = _make_session(run)

    with (
        patch("app.core.worker.AsyncSessionLocal", return_value=session),
        patch("app.core.worker.run_orchestrator", new_callable=AsyncMock) as mock_orch,
    ):
        await orchestrate_run({}, str(run.id))

    mock_orch.assert_called_once_with(run.id, session)
    assert run.status == "ready"
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Exception path: status set to 'failed', exception re-raised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_sets_failed_on_exception():
    run = _make_run(status="analyzing")
    session = _make_session(run)

    with (
        patch("app.core.worker.AsyncSessionLocal", return_value=session),
        patch(
            "app.core.worker.run_orchestrator",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM error"),
        ),
    ):
        with pytest.raises(RuntimeError, match="LLM error"):
            await orchestrate_run({}, str(run.id))

    assert run.status == "failed"
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 4a. Skips silently if run not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_skips_if_run_not_found():
    session = _make_session(run=None)

    with (
        patch("app.core.worker.AsyncSessionLocal", return_value=session),
        patch("app.core.worker.run_orchestrator", new_callable=AsyncMock) as mock_orch,
    ):
        await orchestrate_run({}, str(uuid.uuid4()))

    mock_orch.assert_not_called()
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 4b. Skips silently if run status is not 'analyzing'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_skips_if_status_not_analyzing():
    run = _make_run(status="ready")
    session = _make_session(run)

    with (
        patch("app.core.worker.AsyncSessionLocal", return_value=session),
        patch("app.core.worker.run_orchestrator", new_callable=AsyncMock) as mock_orch,
    ):
        await orchestrate_run({}, str(run.id))

    mock_orch.assert_not_called()
    session.commit.assert_not_called()
