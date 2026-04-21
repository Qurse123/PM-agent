from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.embed import embed_text
from app.rag.retrieve import retrieve_similar_feedback


@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    fake_vec = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_vec)]

    with patch("app.rag.embed.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await embed_text("some feedback reason")

    assert result == fake_vec
    mock_client.embeddings.create.assert_called_once_with(
        input="some feedback reason",
        model="text-embedding-3-small",
        dimensions=1536,
    )


@pytest.mark.asyncio
async def test_retrieve_similar_feedback_uses_vector_when_embeddings_exist():
    fake_vec = [0.0] * 1536
    fe_id = uuid.uuid4()
    proposal_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    row = {
        "id": fe_id,
        "proposal_id": proposal_id,
        "reason": "wrong ticket",
        "category": "wrong_issue",
        "disputed_segment_ids": [],
        "embedding": fake_vec,
        "created_at": now,
    }

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    vector_result = MagicMock()
    vector_result.mappings.return_value.all.return_value = [row]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[count_result, vector_result])

    with patch("app.rag.retrieve.embed_text", return_value=fake_vec):
        results = await retrieve_similar_feedback("transcript text", db, limit=5)

    assert len(results) == 1
    assert results[0].reason == "wrong ticket"


@pytest.mark.asyncio
async def test_retrieve_similar_feedback_falls_back_to_recency_when_no_embeddings():
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    fe = MagicMock()
    fe.reason = "no embedding yet"
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = [fe]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[count_result, scalar_result])

    with patch("app.rag.retrieve.embed_text", return_value=[0.0] * 1536):
        results = await retrieve_similar_feedback("anything", db, limit=5)

    assert len(results) == 1
    assert results[0].reason == "no embedding yet"
