"""Explicit document ingestion and local lexical-search command entry points."""

import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.client import CanvasClient
from app.canvas.courses import _normalize_canvas_id
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.canvas.files import CanvasFileSource
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.documents.config import document_limits
from app.files.downloader import ControlledFileDownloader
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_search import DocumentSearchService
from app.services.file_download import FileDownloadService


async def _ingest(
    settings: Settings,
    *,
    file_id: str | None = None,
    course_id: str | None = None,
    allow_download: bool = False,
    max_download_files: int = 15,
    max_download_bytes: int = 50 * 1024 * 1024,
) -> int:
    initialize_database()
    async with AsyncExitStack() as stack:
        downloader_service: FileDownloadService | None = None
        with get_session_factory()() as session:
            if allow_download:
                base_url = settings.canvas_base_url
                token = resolve_canvas_token(settings)
                if base_url is None or token is None:
                    raise CanvasConfigurationError(
                        "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before downloading"
                    )
                client = await stack.enter_async_context(
                    CanvasClient(
                        base_url=base_url,
                        token=token,
                    )
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
            if file_id is not None:
                outcome = await service.ingest_file(
                    file_id,
                    canvas_course_id=course_id,
                    allow_download=allow_download,
                )
                payload: object = outcome.model_dump(mode="json")
                failed = outcome.status in {"failed", "source_missing", "source_corrupt"}
            else:
                if course_id is None:
                    raise ValueError("course_id is required when file_id is not provided")
                plan = service.plan_course(
                    course_id,
                    max_new_download_files=max_download_files,
                    max_new_download_bytes=max_download_bytes,
                )
                summary = await service.ingest_course(
                    course_id,
                    allow_download=allow_download,
                    max_new_download_files=max_download_files,
                    max_new_download_bytes=max_download_bytes,
                )
                payload = {
                    "plan": plan.model_dump(mode="json"),
                    "summary": summary.model_dump(mode="json"),
                }
                failed = summary.files_failed > 0
    json.dump(payload, sys.stdout, indent=2)
    print()
    return int(failed)


def run_file() -> int:
    parser = argparse.ArgumentParser(description="Ingest one known Canvas academic file")
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--course-id")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    try:
        file_id = _normalize_canvas_id(args.file_id, field_name="file_id")
        course_id = (
            _normalize_canvas_id(args.course_id, field_name="course_id")
            if args.course_id
            else None
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return _run_ingestion(
        file_id=file_id,
        course_id=course_id,
        allow_download=args.download,
    )


def run_course() -> int:
    parser = argparse.ArgumentParser(description="Ingest supported files for one Canvas course")
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--max-download-files", type=int, default=15)
    parser.add_argument("--max-download-bytes", type=int, default=50 * 1024 * 1024)
    args = parser.parse_args()
    if not 0 <= args.max_download_files <= 100:
        parser.error("--max-download-files must be between 0 and 100")
    if not 0 <= args.max_download_bytes <= 500 * 1024 * 1024:
        parser.error("--max-download-bytes must be between 0 and 524288000")
    try:
        course_id = _normalize_canvas_id(args.course_id, field_name="course_id")
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return _run_ingestion(
        course_id=course_id,
        allow_download=args.download,
        max_download_files=args.max_download_files,
        max_download_bytes=args.max_download_bytes,
    )


def _run_ingestion(
    *,
    file_id: str | None = None,
    course_id: str | None = None,
    allow_download: bool,
    max_download_files: int = 15,
    max_download_bytes: int = 50 * 1024 * 1024,
) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(
            _ingest(
                settings,
                file_id=file_id,
                course_id=course_id,
                allow_download=allow_download,
                max_download_files=max_download_files,
                max_download_bytes=max_download_bytes,
            )
        )
    except (CanvasError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


def run_search() -> int:
    parser = argparse.ArgumentParser(description="Search locally parsed academic documents")
    parser.add_argument("query")
    parser.add_argument("--course-id")
    parser.add_argument("--file-id")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    try:
        course_id = (
            _normalize_canvas_id(args.course_id, field_name="course_id")
            if args.course_id
            else None
        )
        file_id = (
            _normalize_canvas_id(args.file_id, field_name="file_id")
            if args.file_id
            else None
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_database()
    with get_session_factory()() as session:
        results = DocumentSearchService(session).search(
            args.query,
            canvas_course_id=course_id,
            canvas_file_id=file_id,
            limit=args.limit,
        )
    json.dump([item.model_dump(mode="json") for item in results], sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_file())
