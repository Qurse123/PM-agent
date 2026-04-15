from contextlib import asynccontextmanager
from typing import AsyncGenerator

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from app.config import settings
from app.models.db import Base, async_engine
from app.api.runs import router as runs_router
from app.api.workspace import router as workspace_router
from app.api.proposals import router as proposals_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield ## everything before is startup
    await app.state.arq_pool.close()


app = FastAPI(title="PM Agent", lifespan=lifespan)
app.include_router(runs_router)
app.include_router(workspace_router)
app.include_router(proposals_router)
## we are including the router since these endpoints would not be active without it


@app.get("/health")  ## get the runs health
async def health() -> dict[str, int]:
    return {"status": 200}
