"""Local read-only composed academic-context diagnostic API."""

from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.academic_context.models import AcademicContext
from app.assistant_tools.models import AcademicContextPackage
from app.assistant_tools.service import AcademicToolService
from app.config import get_settings
from app.course_router.models import CourseRoutingRequest
from app.database.session import get_session
from app.retrieval.assistant_adapter import RetrievalEvidenceAdapter
from app.retrieval.models import RetrievalMode
from app.services.academic_context import AcademicContextService
from app.services.course_profiles import CourseNotFoundError

router = APIRouter(prefix="/api/academic-context", tags=["academic-context"])


@router.post("/resolve", response_model=AcademicContext)
def resolve_context(
    request: CourseRoutingRequest,
    session: Annotated[Session, Depends(get_session)],
) -> AcademicContext:
    try:
        context = AcademicContextService(session).build(request)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc
    if context is None:
        raise HTTPException(status_code=404, detail="course context could not be resolved")
    return context


@router.post("/package", response_model=AcademicContextPackage)
def resolve_context_package(
    request: CourseRoutingRequest,
    session: Annotated[Session, Depends(get_session)],
    mode: RetrievalMode = "lexical",
    limit: Annotated[int, Query(ge=1, le=20)] = 20,
) -> AcademicContextPackage:
    """Compose local course context with verified professor-material evidence."""

    adapter = RetrievalEvidenceAdapter(session, mode=mode, limit=limit)
    package = AcademicToolService(
        session,
        academic_timezone=ZoneInfo(get_settings().academic_timezone),
    ).build_context_package(request, retrieval=adapter)
    if package is None:
        raise HTTPException(status_code=404, detail="course context could not be resolved")
    return package
