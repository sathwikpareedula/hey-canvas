"""CLI for one dependency-aware, read-only unified Canvas synchronization."""

import argparse
import asyncio
import json
import sys
from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.announcements import CanvasAnnouncementSource
from app.canvas.assignments import CanvasAssignmentSource
from app.canvas.client import CanvasClient
from app.canvas.courses import CanvasCourseSource, _normalize_canvas_id
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.canvas.files import CanvasFileSource
from app.canvas.modules import CanvasModuleSource
from app.canvas.syllabus import CanvasSyllabusSource
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.documents.config import document_limits
from app.files.downloader import ControlledFileDownloader
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.announcement_sync import AnnouncementSyncService
from app.services.assignment_sync import AssignmentSyncService
from app.services.course_sync import CourseSyncService
from app.services.document_ingestion import DocumentIngestionService
from app.services.file_download import FileDownloadService
from app.services.file_integrity import FileIntegrityService
from app.services.file_metadata_sync import FileMetadataSyncService
from app.services.module_sync import ModuleSyncService
from app.services.syllabus_sync import SyllabusSyncService
from app.services.sync_orchestrator import UnifiedSyncService


async def synchronize_all(
    settings: Settings,
    *,
    course_ids: list[str],
    check_local_files: bool,
) -> int:
    base_url = settings.canvas_base_url
    token = resolve_canvas_token(settings)
    if base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before unified synchronization"
        )
    normalized = [
        _normalize_canvas_id(course_id, field_name="course_id") for course_id in course_ids
    ]
    initialize_database()
    async with (
        CanvasClient(base_url=base_url, token=token) as client,
        ControlledFileDownloader(
            canvas_base_url=base_url,
            token=token,
            max_bytes=settings.max_canvas_file_bytes,
        ) as binary_downloader,
    ):
        with get_session_factory()() as session:
            downloads = FileDownloadService(
                source=CanvasFileSource(client),
                downloader=binary_downloader,
                session=session,
                storage_root=settings.academic_files_root,
            )
            result = await UnifiedSyncService(
                session=session,
                courses=CourseSyncService(source=CanvasCourseSource(client), session=session),
                assignments=AssignmentSyncService(
                    source=CanvasAssignmentSource(client), session=session
                ),
                modules=ModuleSyncService(source=CanvasModuleSource(client), session=session),
                files=FileMetadataSyncService(
                    source=CanvasFileSource(client),
                    session=session,
                    concurrency=settings.canvas_file_metadata_concurrency,
                ),
                integrity=FileIntegrityService(
                    session=session, storage_root=settings.academic_files_root
                ),
                announcements=AnnouncementSyncService(
                    source=CanvasAnnouncementSource(client), session=session
                ),
                syllabus=SyllabusSyncService(
                    source=CanvasSyllabusSource(client), session=session
                ),
                knowledge=DocumentIngestionService(
                    session=session,
                    storage_root=settings.academic_files_root,
                    limits=document_limits(settings),
                    downloader=downloads,
                ),
                knowledge_max_download_files=settings.knowledge_max_download_files_per_sync,
                knowledge_max_download_bytes=settings.knowledge_max_download_bytes_per_sync,
                stale_after=timedelta(minutes=settings.sync_run_stale_minutes),
            ).run_sync(
                course_ids=normalized or None,
                check_local_files=check_local_files,
                trigger="cli",
            )
    print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if result.status == "succeeded" else 2 if result.status == "partially_succeeded" else 1


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize Canvas courses and academic metadata without downloading files"
    )
    parser.add_argument(
        "--course-id", action="append", default=[], help="Canvas course ID; repeatable"
    )
    parser.add_argument(
        "--check-local-files", action="store_true", help="hash existing local files after sync"
    )
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(
            synchronize_all(
                settings,
                course_ids=args.course_id,
                check_local_files=args.check_local_files,
            )
        )
    except (CanvasError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
