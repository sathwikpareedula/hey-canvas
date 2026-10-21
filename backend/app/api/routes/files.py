"""Local-only Canvas file metadata APIs; these endpoints never download content."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas.files import FileResponse
from app.canvas.courses import _normalize_canvas_id
from app.database.session import get_session
from app.files.models import DownloadState
from app.services.file_query import FileQueryService

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[FileResponse])
def list_files(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    download_state: DownloadState | None = None,
) -> list[FileResponse]:
    return FileQueryService(session).list_files(
        canvas_course_id=_validated_id(course_id, "course_id") if course_id else None,
        download_state=download_state,
    )


@router.get("/{file_id}", response_model=FileResponse)
def get_file(file_id: str, session: Annotated[Session, Depends(get_session)]) -> FileResponse:
    normalized = _validated_id(file_id, "file_id")
    files = FileQueryService(session).list_files(canvas_file_id=normalized)
    if not files:
        raise HTTPException(status_code=404, detail="file not found")
    return files[0]


def _validated_id(value: str, parameter: str) -> str:
    try:
        return _normalize_canvas_id(value, field_name=parameter)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{parameter} is invalid") from exc
