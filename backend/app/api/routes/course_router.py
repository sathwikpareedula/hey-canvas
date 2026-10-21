"""Local read-only course-resolution diagnostic API."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.course_router.models import CourseRoutingRequest, CourseRoutingResult
from app.database.session import get_session
from app.services.course_router import CourseRouterService

router = APIRouter(prefix="/api/course-router", tags=["course-router"])


@router.post("/resolve", response_model=CourseRoutingResult)
def resolve_course(
    request: CourseRoutingRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CourseRoutingResult:
    """Resolve a course from deterministic local signals without network access."""

    return CourseRouterService(session).resolve(request)
