import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.meet import fetch_conference_display_name, fetch_transcript_entries
from app.ingest.parser import parse_transcript
from app.models.db import LinearTeam, Proposal, Run, TranscriptSegment, get_db

router = APIRouter(prefix="/runs", tags=["runs"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PasteRunRequest(BaseModel):
    transcript_text: str
    conference_record_id: str | None = None  # auto-generated as f"paste-{run_id}" if omitted
    title: str | None = None  # optional meeting title; auto-extracted from transcript if omitted
    linear_team_id: str | None = None  # explicit override; auto-matched from title if omitted


class MeetRunRequest(BaseModel):
    conference_record_id: str
    title: str | None = None
    linear_team_id: str | None = None


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
    title: str | None = None
    status: str
    created_at: datetime
    segment_count: int
    proposal_count: int = 0
    pending_proposal_count: int = 0
    linear_team_id: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _count_segments(db: AsyncSession, run_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(TranscriptSegment.id)).where(TranscriptSegment.run_id == run_id)
    )
    return result.scalar_one()


async def _count_proposals(db: AsyncSession, run_id: uuid.UUID) -> tuple[int, int]:
    """Returns (total, pending) proposal counts for a run."""
    result = await db.execute(
        select(
            func.count(Proposal.id),
            func.sum(case((Proposal.status == "pending", 1), else_=0)),
        ).where(Proposal.run_id == run_id)
    )
    total, pending = result.one()
    return (total or 0), (int(pending) if pending else 0)


def _extract_title(text: str) -> str | None:
    """Return the first non-empty line of the transcript if it is not a speaker turn."""
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # A speaker line looks like "Name: text" — short prefix (≤3 words) before a colon
        if ": " in line:
            prefix = line.split(": ", 1)[0]
            if len(prefix.split()) <= 3:
                return None  # transcript starts immediately with dialogue — no title
        return line
    return None


async def _get_teams_as_dicts(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(LinearTeam))
    return [
        {"linear_team_id": t.linear_team_id, "name": t.name, "key": t.key}
        for t in result.scalars().all()
    ]


def _match_team_by_title(title: str, teams: list[dict]) -> str | None:
    """Return linear_team_id of the first team whose name or key appears in the title (case-insensitive)."""
    lowered = title.lower()
    for team in teams:
        if team["name"].lower() in lowered or team["key"].lower() in lowered:
            return team["linear_team_id"]
    return None


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
    access_token = authorization.removeprefix("Bearer ").strip()

    run = Run(
        conference_record_id=request.conference_record_id,
        title=request.title,
        status="ingesting",
    )
    db.add(run)
    await db.flush()

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
        [TranscriptSegment(id=uuid.uuid4(), run_id=run.id, **seg) for seg in segments]
    )
    if not run.title:
        run.title = await fetch_conference_display_name(
            request.conference_record_id, access_token
        )
    run.status = "ready"
    await db.commit()

    return RunResponse(
        id=run.id,
        conference_record_id=run.conference_record_id,
        title=run.title,
        status=run.status,
        created_at=run.created_at,
        segment_count=len(segments),
        proposal_count=0,
        pending_proposal_count=0,
    )


@router.get("", response_model=list[RunResponse])
async def list_runs(
    db: AsyncSession = Depends(get_db),
) -> list[RunResponse]:
    """List all runs ordered by most recent first."""
    result = await db.execute(select(Run).order_by(Run.created_at.desc()))
    runs = result.scalars().all()
    responses = []
    for run in runs:
        seg_count = await _count_segments(db, run.id)
        proposal_count, pending_count = await _count_proposals(db, run.id)
        responses.append(
            RunResponse(
                id=run.id,
                conference_record_id=run.conference_record_id,
                title=run.title,
                status=run.status,
                created_at=run.created_at,
                segment_count=seg_count,
                proposal_count=proposal_count,
                pending_proposal_count=pending_count,
                linear_team_id=run.linear_team_id,
            )
        )
    return responses


@router.post("", response_model=RunResponse, status_code=201)
async def create_run_from_paste(
    request: PasteRunRequest,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Ingest a pasted transcript."""
    run_id = uuid.uuid4()
    title = request.title or _extract_title(request.transcript_text)

    team_id = request.linear_team_id
    if team_id is None and title:
        teams = await _get_teams_as_dicts(db)
        team_id = _match_team_by_title(title, teams)

    run = Run(
        id=run_id,
        conference_record_id=request.conference_record_id or f"paste-{run_id}",
        title=title,
        status="ingesting",
        linear_team_id=team_id,
    )
    db.add(run)
    await db.flush()

    try:
        segments = parse_transcript(request.transcript_text, run.id)
        db.add_all([TranscriptSegment(id=uuid.uuid4(), **seg) for seg in segments])
        run.status = "ready"
        await db.commit()
    except Exception as exc:
        run.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RunResponse(
        id=run.id,
        conference_record_id=run.conference_record_id,
        title=run.title,
        status=run.status,
        created_at=run.created_at,
        segment_count=len(segments),
        proposal_count=0,
        pending_proposal_count=0,
        linear_team_id=run.linear_team_id,
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

    seg_count = await _count_segments(db, run_id)
    proposal_count, pending_count = await _count_proposals(db, run_id)

    return RunResponse(
        id=run.id,
        conference_record_id=run.conference_record_id,
        title=run.title,
        status=run.status,
        created_at=run.created_at,
        segment_count=seg_count,
        proposal_count=proposal_count,
        pending_proposal_count=pending_count,
        linear_team_id=run.linear_team_id,
    )


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await db.delete(run)
    await db.commit()


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
