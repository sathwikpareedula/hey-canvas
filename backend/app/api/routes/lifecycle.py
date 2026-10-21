from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.lifecycle.models import LifecycleResult, LifecycleScope
from app.lifecycle.service import LifecycleService

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])


@router.post("/clear", response_model=LifecycleResult)
def clear_local_state(
    scope: LifecycleScope,
    session: Annotated[Session, Depends(get_session)],
) -> LifecycleResult:
    try:
        return LifecycleService(session).clear(scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
