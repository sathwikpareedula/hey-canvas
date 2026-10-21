"""Command-line entry point for metadata-only Canvas file synchronization."""

import argparse
import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.canvas.files import CanvasFileSource
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.file_metadata_sync import FileMetadataSyncService


async def synchronize_configured_file_metadata(
    settings: Settings, *, canvas_course_id: str | None = None
) -> int:
    base_url = settings.canvas_base_url
    token = resolve_canvas_token(settings)
    if base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before synchronizing file metadata"
        )
    initialize_database()
    async with CanvasClient(
        base_url=base_url,
        token=token,
    ) as client:
        with get_session_factory()() as session:
            summary = await FileMetadataSyncService(
                source=CanvasFileSource(client),
                session=session,
                concurrency=settings.canvas_file_metadata_concurrency,
            ).synchronize(canvas_course_id=canvas_course_id)
    print("[OK] Canvas file metadata synchronization completed. No files were downloaded.")
    for label, value in (
        ("References seen", summary.references_seen),
        ("Unique file IDs", summary.unique_file_ids),
        ("Metadata succeeded", summary.metadata_succeeded),
        ("Metadata failed", summary.metadata_failed),
        ("Files created", summary.files_created),
        ("Files updated", summary.files_updated),
        ("Files unchanged", summary.files_unchanged),
    ):
        print(f"{label + ':':22} {value}")
    for failure in summary.failures:
        print(
            f"[FAILED] File {failure.canvas_file_id}: {failure.error_type} - {failure.message}",
            file=sys.stderr,
        )
    return 1 if summary.metadata_failed else 0


def run() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Canvas file metadata only")
    parser.add_argument("--course-id", help="limit discovery to one Canvas course ID")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(
            synchronize_configured_file_metadata(settings, canvas_course_id=args.course_id)
        )
    except CanvasError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
