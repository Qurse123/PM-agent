from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import Proposal, ProposalCitation, Run, get_db

router = APIRouter(prefix="/runs", tags=["proposals"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CitationResponse(BaseModel):
    id: uuid.UUID
    segment_ids: list[str]
    quote: str
    rationale: str

    model_config = {"from_attributes": True}


class ProposalResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    target: str
    operation: str
    before: dict | None
    after: dict
    status: str
    created_at: datetime
    citations: list[CitationResponse]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# GET /runs/{run_id}/proposals
# ---------------------------------------------------------------------------


@router.get("/{run_id}/proposals", response_model=list[ProposalResponse])
async def list_proposals(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ProposalResponse]:
    result = await db.execute(select(Run).where(Run.id == run_id)) ##worker looking this up to confirm that a run exists
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Run not found")

    proposals_result = await db.execute(
        select(Proposal)
        .where(Proposal.run_id == run_id)
        .options(selectinload(Proposal.citations))
        .order_by(Proposal.created_at.asc())
    )
    proposals = proposals_result.scalars().all()
    return [ProposalResponse.model_validate(p) for p in proposals] ## making sure each row follows the correct pydantic schema 


# ---------------------------------------------------------------------------
# POST /runs/{run_id}/analyze
# ---------------------------------------------------------------------------


@router.post("/{run_id}/analyze", status_code=202)
async def analyze_run(
    run_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}'; must be 'ready' to analyze",
        )

    run.status = "analyzing"
    await db.commit()

    # PHASE C: inject feedback_events context
    arq_pool = request.app.state.arq_pool
    await arq_pool.enqueue_job("orchestrate_run", str(run_id)) ## Pushes a background task into redis queue called orchestrate_run with its run_id 

    return {"status": "queued", "run_id": str(run_id)} ## returns the status of the task with its run_id


# ---------------------------------------------------------------------------
# POST /runs/{run_id}/proposals/{proposal_id}/approve
# ---------------------------------------------------------------------------


@router.post("/{run_id}/proposals/{proposal_id}/approve", response_model=ProposalResponse)
async def approve_proposal(
    run_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    result = await db.execute(
        select(Proposal)
        .where(Proposal.id == proposal_id, Proposal.run_id == run_id) 
        .options(selectinload(Proposal.citations)) ## get the citations aswell that match the run id and proposal_id
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal status is '{proposal.status}'; must be 'pending' to approve",
        )

    proposal.status = "approved"
    await db.commit()
    await db.refresh(proposal)
    return ProposalResponse.model_validate(proposal)


# ---------------------------------------------------------------------------
# POST /runs/{run_id}/proposals/{proposal_id}/deny
# ---------------------------------------------------------------------------


@router.post("/{run_id}/proposals/{proposal_id}/deny", response_model=ProposalResponse)
async def deny_proposal(
    run_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    result = await db.execute(
        select(Proposal)
        .where(Proposal.id == proposal_id, Proposal.run_id == run_id)
        .options(selectinload(Proposal.citations))
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal status is '{proposal.status}'; must be 'pending' to deny",
        )

    proposal.status = "denied"
    await db.commit()
    await db.refresh(proposal)
    return ProposalResponse.model_validate(proposal)
