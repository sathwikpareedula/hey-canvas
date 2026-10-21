"""Local-only academic document state, units, and lexical search endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.database.session import get_session
from app.documents.models import (
    CourseDocumentCoverage,
    DocumentSearchHit,
    DocumentStatus,
    DocumentType,
    DocumentUnitView,
    DocumentView,
)
from app.services.document_query import DocumentQueryService
from app.services.document_search import DocumentSearchService

router = APIRouter(tags=["documents"])


@router.get(
    "/api/courses/{course_id}/document-coverage",
    response_model=CourseDocumentCoverage,
)
def get_course_document_coverage(
    course_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> CourseDocumentCoverage:
    normalized = _validated_id(course_id, "course_id")
    return DocumentQueryService(session).course_coverage(normalized)


@router.get("/api/documents", response_model=list[DocumentView])
def list_documents(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    status: DocumentStatus | None = None,
    document_type: DocumentType | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[DocumentView]:
    return DocumentQueryService(session).list_documents(
        canvas_course_id=_validated_id(course_id, "course_id") if course_id else None,
        status=status,
        detected_type=document_type,
        limit=limit,
    )


@router.get("/api/documents/{file_id}", response_model=DocumentView)
def get_document(
    file_id: str, session: Annotated[Session, Depends(get_session)]
) -> DocumentView:
    normalized = _validated_id(file_id, "file_id")
    documents = DocumentQueryService(session).list_documents(
        canvas_file_id=normalized, limit=1
    )
    if not documents:
        raise HTTPException(status_code=404, detail="document not found")
    return documents[0]


@router.get("/api/documents/{file_id}/units", response_model=list[DocumentUnitView])
def get_document_units(
    file_id: str,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[DocumentUnitView]:
    normalized = _validated_id(file_id, "file_id")
    units = DocumentQueryService(session).units(normalized, limit=limit)
    if units is None:
        raise HTTPException(status_code=404, detail="document not found")
    return units


@router.get("/api/document-search", response_model=list[DocumentSearchHit])
def search_documents(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    file_id: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DocumentSearchHit]:
    return DocumentSearchService(session).search(
        q,
        canvas_course_id=_validated_id(course_id, "course_id") if course_id else None,
        canvas_file_id=_validated_id(file_id, "file_id") if file_id else None,
        limit=limit,
    )


def _validated_id(value: str, parameter: str) -> str:
    try:
        return _normalize_canvas_id(value, field_name=parameter)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{parameter} is invalid") from exc
