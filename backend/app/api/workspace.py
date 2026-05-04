import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.linear import LinearClient
from app.models.db import LinearTeam, WorkspaceContext, get_db

router = APIRouter(prefix="/workspace", tags=["workspace"]) ## use the router decorator with the 


class WorkspaceContextRequest(BaseModel):
    context: str | None = None


class WorkspaceContextResponse(BaseModel):
    id: uuid.UUID
    context: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class LinearTeamResponse(BaseModel):
    linear_team_id: str
    name: str
    key: str
    description: str | None

    model_config = {"from_attributes": True}


@router.get("/teams", response_model=list[LinearTeamResponse])
async def list_teams(db: AsyncSession = Depends(get_db)) -> list[LinearTeamResponse]:
    result = await db.execute(select(LinearTeam).order_by(LinearTeam.name))
    teams = result.scalars().all()
    return [LinearTeamResponse.model_validate(t) for t in teams]


@router.post("/teams/sync", response_model=list[LinearTeamResponse])
async def sync_teams(db: AsyncSession = Depends(get_db)) -> list[LinearTeamResponse]:
    """Fetch all teams from Linear and upsert into local DB."""
    if not settings.linear_api_key:
        raise HTTPException(status_code=400, detail="linear_api_key not configured")
    client = LinearClient(settings.linear_api_key)
    remote_teams = await client.list_teams()

    result = await db.execute(select(LinearTeam))
    existing = {t.linear_team_id: t for t in result.scalars().all()}

    synced: list[LinearTeam] = []
    for t in remote_teams:
        if t["id"] in existing:
            row = existing[t["id"]]
            row.name = t["name"]
            row.key = t["key"]
            row.description = t.get("description") or None
        else:
            row = LinearTeam(
                linear_team_id=t["id"],
                name=t["name"],
                key=t["key"],
                description=t.get("description") or None,
            )
            db.add(row)
        synced.append(row)

    await db.commit()
    for row in synced:
        await db.refresh(row)
    return [LinearTeamResponse.model_validate(row) for row in synced]


@router.get("", response_model=WorkspaceContextResponse)
async def get_workspace(db: AsyncSession = Depends(get_db)) -> WorkspaceContextResponse:
    result = await db.execute(select(WorkspaceContext).limit(1)) ## go get the first workspace id
    workspace = result.scalar_one_or_none() ## return one result or none
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace context not configured")

    try:
        return WorkspaceContextResponse.model_validate(workspace)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Workspace row failed response validation",
                "errors": exc.errors(),
            },
        ) from exc


@router.put("", response_model=WorkspaceContextResponse)
async def upsert_workspace(
    request: WorkspaceContextRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContextResponse:
    result = await db.execute(select(WorkspaceContext).limit(1))
    workspace = result.scalar_one_or_none()

    if workspace is None:
        workspace = WorkspaceContext(context=request.context) ## build a new row under context coloumn in workspace context table fill that one row with WorkspaceContextRequest
        db.add(workspace)
    else:
        workspace.context = request.context ## else updating the exisitng conext with request.context value
        workspace.updated_at = datetime.now(timezone.utc)

    await db.commit() ## commit this change to the DB 
    await db.refresh(workspace) ## refresh the DB 
    try:
        return WorkspaceContextResponse.model_validate(workspace)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Update Workspace row failed response validation",
                "errors": exc.errors(),
            },
        ) from exc