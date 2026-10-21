"""Academic knowledge coverage inventory and background preparation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.database.session import get_session
from app.services.knowledge_coverage import (
    KnowledgeCoverageService,
    KnowledgeCoverageSummary,
    KnowledgePreparationStatus,
    get_preparation_status,
    trigger_knowledge_preparation,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class PrepareRequest(BaseModel):
    course_ids: list[str] | None = None
    allow_download: bool = True


class PrepareResponse(BaseModel):
    accepted: bool
    message: str


@router.get("/coverage", response_model=KnowledgeCoverageSummary)
def get_knowledge_coverage(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
) -> KnowledgeCoverageSummary:
    normalized_course = None
    if course_id:
        try:
            normalized_course = _normalize_canvas_id(course_id, field_name="course_id")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="course_id is invalid") from exc

    return KnowledgeCoverageService(session).get_coverage(course_id=normalized_course)


@router.get("/status", response_model=KnowledgePreparationStatus)
def get_preparation_progress() -> KnowledgePreparationStatus:
    return get_preparation_status()


@router.post("/prepare", response_model=PrepareResponse)
def prepare_knowledge_base(
    request: PrepareRequest | None = None,
) -> PrepareResponse:
    req = request or PrepareRequest()
    accepted, message = trigger_knowledge_preparation(
        course_ids=req.course_ids,
        allow_download=req.allow_download,
    )
    return PrepareResponse(accepted=accepted, message=message)
