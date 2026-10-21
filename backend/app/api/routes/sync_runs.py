"""Read-only local synchronization run history endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.services.sync_run_query import SyncRunQueryService
from app.sync.models import SyncRunStatus, SyncRunView

router = APIRouter(prefix="/api/sync-runs", tags=["sync-runs"])


@router.get("", response_model=list[SyncRunView])
def list_sync_runs(
    session: Annotated[Session, Depends(get_session)],
    status: SyncRunStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SyncRunView]:
    return SyncRunQueryService(session).list_runs(status=status, limit=limit)


@router.get("/{run_id}", response_model=SyncRunView)
def get_sync_run(run_id: int, session: Annotated[Session, Depends(get_session)]) -> SyncRunView:
    result = SyncRunQueryService(session).get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="sync run not found")
    return result
