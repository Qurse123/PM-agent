import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import WorkspaceContext, get_db

router = APIRouter(prefix="/workspace", tags=["workspace"]) ## use the router decorator with the 


class WorkspaceContextRequest(BaseModel):
    context: str | None = None


class WorkspaceContextResponse(BaseModel):
    id: uuid.UUID
    context: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


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