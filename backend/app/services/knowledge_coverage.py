"""Course-scoped academic knowledge coverage and preparation inventory."""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.canvas.client import CanvasClient
from app.canvas.files import CanvasFileSource
from app.config import get_settings
from app.database.models import (
    AcademicDocument,
    Assignment,
    CanvasAnnouncement,
    CanvasFile,
    Course,
    CourseMaterialReference,
    CourseModule,
    CourseSyllabus,
    FocusCourse,
    ModuleItem,
)
from app.database.session import get_session_factory
from app.documents.config import document_limits
from app.files.downloader import ControlledFileDownloader
from app.security.canvas_credentials import resolve_canvas_token
from app.services.document_ingestion import DocumentIngestionService
from app.services.file_download import FileDownloadService

logger = logging.getLogger(__name__)


class CourseKnowledgeCoverage(BaseModel):
    course_id: str
    course_name: str | None
    course_code: str | None
    is_focus: bool
    assignments_count: int
    announcements_count: int
    has_syllabus: bool
    modules_count: int
    module_items_count: int
    files_total: int
    files_downloaded: int
    files_parsed: int
    files_needs_ocr: int
    files_unsupported: int
    files_failed: int
    files_unprepared: int
    units_indexed: int
    characters_indexed: int


class KnowledgeCoverageSummary(BaseModel):
    courses_total: int
    focus_courses_total: int
    assignments_total: int
    announcements_total: int
    syllabi_total: int
    modules_total: int
    module_items_total: int
    files_total: int
    files_downloaded: int
    files_parsed: int
    files_needs_ocr: int
    files_unsupported: int
    files_failed: int
    files_unprepared: int
    total_units_indexed: int
    total_characters_indexed: int
    courses: list[CourseKnowledgeCoverage]


class KnowledgePreparationStatus(BaseModel):
    is_preparing: bool
    current_course_id: str | None = None
    current_file_id: str | None = None
    current_file_name: str | None = None
    files_processed: int = 0
    files_total: int = 0
    files_newly_parsed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


_PREPARE_LOCK = threading.Lock()
_CURRENT_STATUS = KnowledgePreparationStatus(is_preparing=False)


def get_preparation_status() -> KnowledgePreparationStatus:
    return _CURRENT_STATUS


class KnowledgeCoverageService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_coverage(self, *, course_id: str | None = None) -> KnowledgeCoverageSummary:
        focus_course_ids = set(
            self._session.scalars(select(FocusCourse.course_id)).all()
        )
        course_query = select(Course).order_by(Course.course_name)
        if course_id:
            course_query = course_query.where(Course.canvas_course_id == course_id)
        courses = self._session.scalars(course_query).all()

        courses_breakdown: list[CourseKnowledgeCoverage] = []
        for c in courses:
            cid = c.canvas_course_id
            is_focus = cid in focus_course_ids

            assign_cnt = self._session.scalar(
                select(func.count(Assignment.id)).where(Assignment.course_id == c.id)
            ) or 0
            ann_cnt = self._session.scalar(
                select(func.count(CanvasAnnouncement.id)).where(
                    CanvasAnnouncement.course_id == c.id
                )
            ) or 0
            syl_cnt = self._session.scalar(
                select(func.count(CourseSyllabus.id)).where(CourseSyllabus.course_id == c.id)
            ) or 0
            mod_cnt = self._session.scalar(
                select(func.count(CourseModule.id)).where(CourseModule.course_id == c.id)
            ) or 0
            mod_item_cnt = self._session.scalar(
                select(func.count(ModuleItem.id))
                .join(CourseModule, ModuleItem.module_id == CourseModule.id)
                .where(CourseModule.course_id == c.id)
            ) or 0

            # Course files through references
            file_ids = set(
                self._session.scalars(
                    select(CourseMaterialReference.canvas_file_id).where(
                        CourseMaterialReference.course_id == cid
                    )
                ).all()
            )
            files_total = len(file_ids)

            files_downloaded = 0
            files_parsed = 0
            files_needs_ocr = 0
            files_unsupported = 0
            files_failed = 0
            units_indexed = 0
            chars_indexed = 0

            if file_ids:
                files_downloaded = self._session.scalar(
                    select(func.count(CanvasFile.id)).where(
                        CanvasFile.canvas_file_id.in_(file_ids),
                        CanvasFile.download_state == "downloaded",
                    )
                ) or 0

                doc_rows = self._session.scalars(
                    select(AcademicDocument).where(
                        AcademicDocument.canvas_file_id.in_(file_ids)
                    )
                ).all()

                for doc in doc_rows:
                    if doc.last_attempt_status == "parsed":
                        files_parsed += 1
                        units_indexed += doc.unit_count or 0
                        chars_indexed += doc.character_count or 0
                    elif doc.last_attempt_status == "needs_ocr":
                        files_needs_ocr += 1
                        units_indexed += doc.unit_count or 0
                    elif doc.last_attempt_status == "unsupported":
                        files_unsupported += 1
                    else:
                        files_failed += 1

            files_unprepared = max(
                0, files_total - (files_parsed + files_needs_ocr + files_unsupported)
            )

            courses_breakdown.append(
                CourseKnowledgeCoverage(
                    course_id=cid,
                    course_name=c.course_name,
                    course_code=c.course_code,
                    is_focus=is_focus,
                    assignments_count=assign_cnt,
                    announcements_count=ann_cnt,
                    has_syllabus=syl_cnt > 0,
                    modules_count=mod_cnt,
                    module_items_count=mod_item_cnt,
                    files_total=files_total,
                    files_downloaded=files_downloaded,
                    files_parsed=files_parsed,
                    files_needs_ocr=files_needs_ocr,
                    files_unsupported=files_unsupported,
                    files_failed=files_failed,
                    files_unprepared=files_unprepared,
                    units_indexed=units_indexed,
                    characters_indexed=chars_indexed,
                )
            )

        return KnowledgeCoverageSummary(
            courses_total=len(courses),
            focus_courses_total=len(focus_course_ids),
            assignments_total=sum(c.assignments_count for c in courses_breakdown),
            announcements_total=sum(c.announcements_count for c in courses_breakdown),
            syllabi_total=sum(1 for c in courses_breakdown if c.has_syllabus),
            modules_total=sum(c.modules_count for c in courses_breakdown),
            module_items_total=sum(c.module_items_count for c in courses_breakdown),
            files_total=sum(c.files_total for c in courses_breakdown),
            files_downloaded=sum(c.files_downloaded for c in courses_breakdown),
            files_parsed=sum(c.files_parsed for c in courses_breakdown),
            files_needs_ocr=sum(c.files_needs_ocr for c in courses_breakdown),
            files_unsupported=sum(c.files_unsupported for c in courses_breakdown),
            files_failed=sum(c.files_failed for c in courses_breakdown),
            files_unprepared=sum(c.files_unprepared for c in courses_breakdown),
            total_units_indexed=sum(c.units_indexed for c in courses_breakdown),
            total_characters_indexed=sum(c.characters_indexed for c in courses_breakdown),
            courses=courses_breakdown,
        )


async def execute_knowledge_preparation(
    *,
    course_ids: list[str] | None = None,
    allow_download: bool = True,
    max_files_per_course: int = 15,
    max_bytes_per_course: int = 50 * 1024 * 1024,
) -> None:
    global _CURRENT_STATUS
    settings = get_settings()
    started_at = datetime.now(UTC)

    _CURRENT_STATUS = KnowledgePreparationStatus(
        is_preparing=True,
        started_at=started_at,
    )

    try:
        async with AsyncExitStack() as stack:
            factory = get_session_factory()
            with factory() as session:
                if course_ids:
                    target_courses = course_ids
                else:
                    focus = session.scalars(select(FocusCourse.course_id)).all()
                    target_courses = list(focus) if focus else []
                    if not target_courses:
                        # Fallback to active courses
                        active = session.scalars(
                            select(Course.canvas_course_id).where(
                                Course.enrollment_state == "active"
                            )
                        ).all()
                        target_courses = list(active)

                downloader_service: FileDownloadService | None = None
                if allow_download:
                    base_url = settings.canvas_base_url
                    token = resolve_canvas_token(settings)
                    if base_url and token:
                        client = await stack.enter_async_context(
                            CanvasClient(base_url=base_url, token=token)
                        )
                        binary_downloader = await stack.enter_async_context(
                            ControlledFileDownloader(
                                canvas_base_url=base_url,
                                token=token,
                                max_bytes=settings.max_canvas_file_bytes,
                            )
                        )
                        downloader_service = FileDownloadService(
                            source=CanvasFileSource(client),
                            downloader=binary_downloader,
                            session=session,
                            storage_root=settings.academic_files_root,
                        )

                service = DocumentIngestionService(
                    session=session,
                    storage_root=settings.academic_files_root,
                    limits=document_limits(settings),
                    downloader=downloader_service,
                )

                # Total eligible files to prepare
                total_files_to_process = 0
                course_plans: dict[str, Any] = {}
                for cid in target_courses:
                    plan = service.plan_course(
                        cid,
                        max_new_download_files=max_files_per_course,
                        max_new_download_bytes=max_bytes_per_course,
                    )
                    course_plans[cid] = plan
                    total_files_to_process += plan.eligible_files

                _CURRENT_STATUS.files_total = total_files_to_process

                for cid in target_courses:
                    _CURRENT_STATUS.current_course_id = cid
                    plan = course_plans[cid]
                    eligible = service._eligible_course_files(cid)
                    allowed_downloads: list[str] = []
                    bytes_planned = 0
                    if allow_download and downloader_service:
                        for record in eligible:
                            if service._local_source(record)[0] is not None:
                                continue
                            if record.size is None:
                                continue
                            if len(allowed_downloads) >= max_files_per_course:
                                continue
                            if bytes_planned + record.size > max_bytes_per_course:
                                continue
                            allowed_downloads.append(record.canvas_file_id)
                            bytes_planned += record.size

                    allowed_set = set(allowed_downloads)
                    for record in eligible:
                        fid = record.canvas_file_id
                        _CURRENT_STATUS.current_file_id = fid
                        _CURRENT_STATUS.current_file_name = record.display_name or record.filename

                        outcome = await service.ingest_file(
                            fid,
                            canvas_course_id=cid,
                            allow_download=fid in allowed_set,
                        )
                        _CURRENT_STATUS.files_processed += 1
                        if outcome.skipped:
                            _CURRENT_STATUS.files_skipped += 1
                        elif outcome.parsed:
                            _CURRENT_STATUS.files_newly_parsed += 1
                        elif outcome.status in {"failed", "source_corrupt", "source_missing"}:
                            _CURRENT_STATUS.files_failed += 1

                _CURRENT_STATUS.finished_at = datetime.now(UTC)
                _CURRENT_STATUS.is_preparing = False

    except Exception as exc:
        logger.exception("Knowledge preparation failed: %s", exc)
        _CURRENT_STATUS.is_preparing = False
        _CURRENT_STATUS.finished_at = datetime.now(UTC)
        _CURRENT_STATUS.error = str(exc)
    finally:
        if _PREPARE_LOCK.locked():
            _PREPARE_LOCK.release()


def trigger_knowledge_preparation(
    *,
    course_ids: list[str] | None = None,
    allow_download: bool = True,
) -> tuple[bool, str]:
    if not _PREPARE_LOCK.acquire(blocking=False):
        return False, "Knowledge base preparation is already running on this machine."

    # Run in background event loop/thread
    thread = threading.Thread(
        target=lambda: asyncio.run(
            execute_knowledge_preparation(
                course_ids=course_ids,
                allow_download=allow_download,
            )
        ),
        daemon=True,
    )
    thread.start()
    return True, "Knowledge base preparation started in background."
