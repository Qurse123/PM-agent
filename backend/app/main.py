from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.models.db import Base, async_engine
from app.api.runs import router as runs_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="PM Agent", lifespan=lifespan)
app.include_router(runs_router)


@app.get("/health") ## get the runs health
async def health() -> dict[str, int]:
    return {"status": 200}
