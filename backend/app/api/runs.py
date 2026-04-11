import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.meet import fetch_transcript_entries
from app.ingest.parser import parse_transcript
from app.models.db import Run, TranscriptSegment, get_db

router = APIRouter(prefix="/runs", tags=["runs"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PasteRunRequest(BaseModel):
    transcript_text: str
    conference_record_id: str | None = None  # auto-generated as f"paste-{run_id}" if omitted


class MeetRunRequest(BaseModel):
    conference_record_id: str


class SegmentResponse(BaseModel):
    segment_id: str
    start_ms: int | None
    end_ms: int | None
    speaker_ref: str | None
    text: str

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: uuid.UUID
    conference_record_id: str
    status: str
    created_at: datetime
    segment_count: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helper: count segments for a run
# ---------------------------------------------------------------------------


async def _count_segments(db: AsyncSession, run_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(TranscriptSegment.id)).where(TranscriptSegment.run_id == run_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Routes (order matters: specific paths before parameterised ones)
# ---------------------------------------------------------------------------


@router.post("/from-meet", response_model=RunResponse, status_code=201)
async def create_run_from_meet(
    request: MeetRunRequest,
    authorization: str = Header(...), 
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Ingest a transcript directly from the Google Meet REST API."""
    if not authorization.startswith("Bearer"):
        raise HTTPException(status_code=401, detail="Authorization header must start with 'Bearer '")
    access_token = authorization.removeprefix("Bearer") ## in order to get the value of just the token 

    run = Run(conference_record_id=request.conference_record_id, status="ingesting")
    db.add(run)
    await db.flush()  # populate run.id without committing 

    try:
        segments = await fetch_transcript_entries(
            conference_record_id=request.conference_record_id,
            access_token=access_token,
        )
    except httpx.HTTPStatusError as exc:
        run.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Meet API error {exc.response.status_code}: {exc.response.text}",
        ) from exc
    except Exception as exc:
        run.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db.add_all(
        [
            TranscriptSegment(
                id=uuid.uuid4(),
                run_id=run.id,
                **seg,
            )
            for seg in segments
        ]
    )
    run.status = "ready"
    await db.commit()

    return RunResponse(
        id=run.id,
        conference_record_id=run.conference_record_id,
        status=run.status,
        created_at=run.created_at,
        segment_count=len(segments),
    )

@router.post("", response_model=RunResponse, status_code=201)
async def create_run_from_paste(
    request: PasteRunRequest,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Ingest a pasted transcript."""
    run = Run(
        conference_record_id=request.conference_record_id,
        status="ingesting",
    )
    db.add(run)
    await db.flush()  # populate run.id

    # Back-fill auto-generated conference_record_id if not provided
    if not request.conference_record_id:
        run.conference_record_id = f"paste-{run.id}"

    try:
        segments = parse_transcript(request.transcript_text, run.id)

        db.add_all(
            [
                TranscriptSegment(
                    id=uuid.uuid4(),
                    run_id=run.id,
                    **seg,
                )
                for seg in segments
            ]
        )
        run.status = "ready"
        await db.commit()
    except Exception as exc:
        run.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RunResponse(
        id=run.id,
        conference_record_id=run.conference_record_id,
        status=run.status,
        created_at=run.created_at,
        segment_count=len(segments),
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Fetch a single run by ID."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    segment_count = await _count_segments(db, run_id)

    return RunResponse(
        id=run.id,
        conference_record_id=run.conference_record_id,
        status=run.status,
        created_at=run.created_at,
        segment_count=segment_count,
    )


@router.get("/{run_id}/segments", response_model=list[SegmentResponse])
async def get_run_segments(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SegmentResponse]:
    """Return all transcript segments for a run, ordered by segment_id."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    seg_result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.run_id == run_id)
        .order_by(TranscriptSegment.start_ms.asc().nulls_last(), TranscriptSegment.id.asc())
    )
    segments = seg_result.scalars().all()
    return [SegmentResponse.model_validate(s) for s in segments]