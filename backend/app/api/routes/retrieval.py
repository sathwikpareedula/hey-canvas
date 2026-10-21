"""Local-only provenance-aware retrieval and context-packaging endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.database.session import get_session
from app.retrieval.models import (
    RetrievalContextPackage,
    RetrievalMode,
    RetrievalResponse,
    SourceDetail,
    UnitNeighborhood,
)
from app.services.retrieval import RetrievalService
from app.services.retrieval_context import RetrievalContextPackager
from app.services.retrieval_tools import AcademicRetrievalTools

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.get("/search", response_model=RetrievalResponse)
def search(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    file_id: Annotated[str | None, Query(max_length=255)] = None,
    mode: RetrievalMode = "lexical",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RetrievalResponse:
    return RetrievalService(session).search(
        q,
        canvas_course_id=_validated_id(course_id, "course_id"),
        canvas_file_id=_validated_id(file_id, "file_id"),
        mode=mode,
        limit=limit,
    )


@router.get("/context", response_model=RetrievalContextPackage)
def context_package(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    file_id: Annotated[str | None, Query(max_length=255)] = None,
    mode: RetrievalMode = "lexical",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    max_characters: Annotated[int, Query(ge=1, le=100_000)] = 12_000,
) -> RetrievalContextPackage:
    response = RetrievalService(session).search(
        q,
        canvas_course_id=_validated_id(course_id, "course_id"),
        canvas_file_id=_validated_id(file_id, "file_id"),
        mode=mode,
        limit=limit,
    )
    return RetrievalContextPackager().package(
        response, max_characters=max_characters, max_items=limit
    )


@router.get(
    "/documents/{file_id}/units/{unit_index}/context",
    response_model=UnitNeighborhood,
)
def unit_context(
    file_id: str,
    unit_index: int,
    session: Annotated[Session, Depends(get_session)],
    before: Annotated[int, Query(ge=0, le=10)] = 1,
    after: Annotated[int, Query(ge=0, le=10)] = 1,
    max_characters: Annotated[int, Query(ge=1, le=50_000)] = 12_000,
) -> UnitNeighborhood:
    result = AcademicRetrievalTools(session).retrieve_unit_context(
        _required_id(file_id, "file_id"),
        unit_index,
        before=before,
        after=after,
        max_characters=max_characters,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="document unit not found")
    return result


@router.get("/documents/{file_id}/source", response_model=SourceDetail)
def source_detail(
    file_id: str,
    session: Annotated[Session, Depends(get_session)],
    citation_limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SourceDetail:
    result = AcademicRetrievalTools(session).retrieve_source_detail(
        _required_id(file_id, "file_id"), citation_limit=citation_limit
    )
    if result is None:
        raise HTTPException(status_code=404, detail="document not found")
    return result


def _validated_id(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    return _required_id(value, name)


def _required_id(value: str, name: str) -> str:
    try:
        return _normalize_canvas_id(value, field_name=name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{name} is invalid") from exc
