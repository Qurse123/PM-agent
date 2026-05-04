from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.integrations.linear import LinearClient
from app.models.db import FeedbackEvent, Proposal, Run, get_db
from app.rag.embed import embed_text

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


class DenyRequest(BaseModel):
    reason: str
    category: str  # free-form: e.g. "wrong ticket", "misread transcript", "team policy"
    disputed_segment_ids: list[str] = []


# ---------------------------------------------------------------------------
# GET /runs/{run_id}/proposals
# ---------------------------------------------------------------------------


@router.get("/{run_id}/proposals", response_model=list[ProposalResponse])
async def list_proposals(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ProposalResponse]:
    result = await db.execute(select(Run).where(Run.id == run_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Run not found")

    proposals_result = await db.execute(
        select(Proposal)
        .where(Proposal.run_id == run_id)
        .options(selectinload(Proposal.citations))
        .order_by(Proposal.created_at.asc())
    )
    proposals = proposals_result.scalars().all()
    return [ProposalResponse.model_validate(p) for p in proposals]


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

    arq_pool = request.app.state.arq_pool
    await arq_pool.enqueue_job("orchestrate_run", str(run_id))

    return {"status": "queued", "run_id": str(run_id)}


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
        .options(selectinload(Proposal.citations))
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
    await db.flush()

    linear = LinearClient(settings.linear_api_key)
    try:
        if proposal.operation == "create":
            after = proposal.after
            await linear.create_issue(
                title=after["title"],
                description=after.get("description", ""),
                team_id=after["teamId"],
            )
        elif proposal.operation == "update":
            if proposal.before is None or "id" not in proposal.before:
                raise HTTPException(
                    status_code=400,
                    detail="Update proposals must include before.id",
                )
            issue_id = proposal.before["id"]
            await linear.update_issue(issue_id, proposal.after)
        proposal.status = "applied"
    except Exception:
        proposal.status = "failed"
        raise

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
    body: DenyRequest,
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
    embedding = await embed_text(f"{body.category}: {body.reason}")
    feedback = FeedbackEvent(
        proposal_id=proposal.id,
        reason=body.reason,
        category=body.category,
        disputed_segment_ids=body.disputed_segment_ids,
        embedding=embedding,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(proposal)
    return ProposalResponse.model_validate(proposal)


# ---------------------------------------------------------------------------
# POST /runs/{run_id}/proposals/approve-all
# ---------------------------------------------------------------------------


@router.post("/{run_id}/proposals/approve-all")
async def approve_all_proposals(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Run).where(Run.id == run_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Run not found")

    pending_result = await db.execute(
        select(Proposal)
        .where(Proposal.run_id == run_id, Proposal.status == "pending")
        .options(selectinload(Proposal.citations))
        .order_by(Proposal.created_at.asc())
    )
    proposals = list(pending_result.scalars().all())

    approved = 0
    failed = 0
    results = []
    linear = LinearClient(settings.linear_api_key)

    for proposal in proposals:
        proposal.status = "approved"
        await db.flush()
        try:
            if proposal.operation == "create":
                after = proposal.after
                await linear.create_issue(
                    title=after["title"],
                    description=after.get("description", ""),
                    team_id=after["teamId"],
                )
            elif proposal.operation == "update":
                if proposal.before is None or "id" not in proposal.before:
                    raise ValueError("Update proposals must include before.id")
                await linear.update_issue(proposal.before["id"], proposal.after)
            proposal.status = "applied"
            approved += 1
            results.append({"id": str(proposal.id), "status": "applied"})
        except Exception as exc:
            proposal.status = "failed"
            failed += 1
            results.append({"id": str(proposal.id), "status": "failed", "error": str(exc)})

    await db.commit()
    return {"approved": approved, "failed": failed, "results": results}
