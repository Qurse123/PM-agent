from __future__ import annotations

import uuid

from arq.connections import RedisSettings
from sqlalchemy import select

from app.config import settings
from app.core.orchestrator import run_orchestrator
from app.models.db import AsyncSessionLocal, Run


async def orchestrate_run(ctx: dict, run_id_str: str) -> None:
    """arq job: run the orchestrator for a given run_id."""
    run_id = uuid.UUID(run_id_str) ## casts thr run id string into a uuid and save in in run id 
    async with AsyncSessionLocal() as db: 
        result = await db.execute(select(Run).where(Run.id == run_id)) ## go to runs table and look for row where the run.id value == run_id
        run = result.scalar_one_or_none() ## return the row or raise an None
        if run is None or run.status != "analyzing": 
            return 
        try:
            await run_orchestrator(run_id, db) ## run the run_orch funtion 
            run.status = "ready"
        except Exception:
            run.status = "failed"
            raise 
        finally:
            await db.commit() ## commit run status change


class WorkerSettings:
    functions = [orchestrate_run] ## this is where the jobs are queued
    redis_settings = RedisSettings.from_dsn(settings.redis_url) ## connect the worker to the redis through redis URL
