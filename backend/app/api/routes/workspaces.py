"""Course workspace and continuity APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.workspaces.models import WorkspaceUpdate, WorkspaceView
from app.workspaces.service import WorkspaceService

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=tuple[WorkspaceView, ...])
def list_workspaces(
    session: Annotated[Session, Depends(get_session)],
    course_id: str | None = Query(default=None, max_length=255),
) -> tuple[WorkspaceView, ...]:
    return WorkspaceService(session).list(course_id=course_id)


@router.put("/{workspace_key}", response_model=WorkspaceView)
def update_workspace(
    workspace_key: str,
    request: WorkspaceUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> WorkspaceView:
    try:
        return WorkspaceService(session).update(workspace_key, request)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{workspace_key}", response_model=WorkspaceView)
def get_or_create_workspace(
    workspace_key: str,
    session: Annotated[Session, Depends(get_session)],
    course_id: str | None = Query(default=None, max_length=255),
    display_name: str | None = Query(default=None, max_length=255),
) -> WorkspaceView:
    try:
        return WorkspaceService(session).get_or_create(
            workspace_key, course_id=course_id, display_name=display_name
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
