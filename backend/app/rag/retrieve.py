from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import FeedbackEvent
from app.rag.embed import embed_text


async def retrieve_similar_feedback(
    query_text: str,
    db: AsyncSession,
    limit: int = 10,
) -> list[FeedbackEvent]:
    """
    Return feedback events most semantically similar to query_text.
    Falls back to recency order if no embeddings exist yet.
    """
    query_vec = await embed_text(query_text)

    # Check if any rows have embeddings
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM feedback_events WHERE embedding IS NOT NULL") ## select a value from feedback_event where the embedding coloumn is not null
    )
    has_embeddings = (count_result.scalar() or 0) > 0

    if has_embeddings:
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]" ## turns python list to pgvector style strings
        result = await db.execute(
            text(
                "SELECT * FROM feedback_events "
                "WHERE embedding IS NOT NULL "
                "ORDER BY embedding <=> CAST(:vec AS vector) " ## order by distance between each rows embeddings and input vector --> converts bound string to vector type
                "LIMIT :limit" ## return top N nearest rows
            ).bindparams(vec=vec_literal, limit=limit) 
        )
        rows = result.mappings().all()
        return [FeedbackEvent(**dict(row)) for row in rows] ## Unpack each row into normal dicts then upack the dicts into keyword args for each row in rows list created a list of feedbackevent objects per DB row

    # Fallback: recency
    result = await db.execute(
        select(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
