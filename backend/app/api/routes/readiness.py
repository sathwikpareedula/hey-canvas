from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_session
from app.readiness.models import ReadinessResponse
from app.readiness.service import ReadinessService

router = APIRouter(prefix="/api/readiness", tags=["system"])


@router.get("", response_model=ReadinessResponse)
def readiness(session: Annotated[Session, Depends(get_session)]) -> ReadinessResponse:
    return ReadinessService(session, get_settings()).check()
