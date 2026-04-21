from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings

_MODEL = "text-embedding-3-small"
_DIMS = 1536


async def embed_text(text: str) -> list[float]:
    """Embed text using OpenAI text-embedding-3-small. Returns a 1536-dim vector."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(input=text, model=_MODEL, dimensions=_DIMS) ## create a vector embedding for text which is a string and store it in response
    return response.data[0].embedding ## return the list of embeddings created by the model in the 0 index (the first one) from the list of embeddings which are all float values
