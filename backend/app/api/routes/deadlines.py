"""Deterministic local deadline API."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes.assignments import _validate_course_filter
from app.api.schemas.assignments import AssignmentResponse
from app.config import get_settings
from app.database.assignment_repository import AssignmentRepository
from app.database.session import get_session
from app.services.deadlines import DeadlineService, DeadlineWindow

router = APIRouter(prefix="/api/deadlines", tags=["deadlines"])

DeadlineClock = Callable[[], datetime]


def get_deadline_clock() -> DeadlineClock:
    """Provide an overrideable aware clock for deterministic API tests."""

    return lambda: datetime.now(UTC)


@router.get("", response_model=list[AssignmentResponse])
def list_deadlines(
    window: DeadlineWindow,
    session: Annotated[Session, Depends(get_session)],
    clock: Annotated[DeadlineClock, Depends(get_deadline_clock)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
) -> list[AssignmentResponse]:
    """Query one precisely defined deadline window from local persistence."""

    settings = get_settings()
    assignments = DeadlineService(
        AssignmentRepository(session),
        academic_timezone=ZoneInfo(settings.academic_timezone),
        clock=clock,
    ).query(window, canvas_course_id=_validate_course_filter(course_id))
    return [AssignmentResponse.model_validate(item) for item in assignments]
