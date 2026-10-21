"""FastAPI endpoints for managed local storage visibility and maintenance."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.services.storage_service import (
    CourseStoragePreview,
    StorageCleanupRequest,
    StorageCleanupResult,
    StorageManagementService,
    StorageSummary,
)

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.get("/summary", response_model=StorageSummary)
def get_storage_summary(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StorageSummary:
    """Return an exhaustive breakdown of local database, cached binaries, and indexed units."""
    service = StorageManagementService(session, settings)
    return service.get_summary()


@router.get("/preview/{course_id}", response_model=CourseStoragePreview)
def get_course_storage_preview(
    course_id: str,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CourseStoragePreview:
    """Return course-scoped preparation preview and estimated download size."""
    service = StorageManagementService(session, settings)
    return service.course_preview(course_id)


@router.post("/cleanup", response_model=StorageCleanupResult)
def cleanup_storage(
    request: StorageCleanupRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StorageCleanupResult:
    """Safely prune temporary download files (.part) and unreferenced orphan files."""
    service = StorageManagementService(session, settings)
    return service.cleanup(
        remove_temp_files=request.remove_temp_files,
        remove_orphans=request.remove_orphans,
        confirm=request.confirm,
    )
