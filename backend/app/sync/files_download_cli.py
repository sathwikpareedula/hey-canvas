"""Command-line entry point for explicit single-file controlled downloads."""

import argparse
import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.canvas.files import CanvasFileSource
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.files.downloader import ControlledFileDownloader
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.file_download import FileDownloadService


async def download_configured_file(
    settings: Settings,
    *,
    canvas_file_id: str,
    canvas_course_id: str | None = None,
    force: bool = False,
) -> int:
    base_url = settings.canvas_base_url
    token = resolve_canvas_token(settings)
    if base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before downloading Canvas files"
        )
    initialize_database()
    async with (
        CanvasClient(base_url=base_url, token=token) as client,
        ControlledFileDownloader(
            canvas_base_url=base_url,
            token=token,
            max_bytes=settings.max_canvas_file_bytes,
        ) as downloader,
    ):
        with get_session_factory()() as session:
            summary = await FileDownloadService(
                source=CanvasFileSource(client),
                downloader=downloader,
                session=session,
                storage_root=settings.academic_files_root,
            ).download(
                canvas_file_id=canvas_file_id,
                canvas_course_id=canvas_course_id,
                force=force,
            )
    if summary.files_selected == 0:
        print(
            "[ERROR] No synchronized file matched the requested filters. "
            "Run canvas-sync-file-metadata first.",
            file=sys.stderr,
        )
        return 1
    print("[OK] Controlled Canvas file download completed.")
    for label, value in (
        ("Files selected", summary.files_selected),
        ("Files downloaded", summary.files_downloaded),
        ("Files skipped", summary.files_skipped),
        ("Files failed", summary.files_failed),
        ("Files too large", summary.files_too_large),
        ("Files inaccessible", summary.files_inaccessible),
    ):
        print(f"{label + ':':20} {value}")
    return 1 if summary.files_failed or summary.files_too_large or summary.files_inaccessible else 0


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Download exactly one synchronized Canvas file safely"
    )
    parser.add_argument("--file-id", required=True, help="Canvas file ID to download")
    parser.add_argument("--course-id", help="require a reference from this Canvas course")
    parser.add_argument("--force", action="store_true", help="replace an otherwise current copy")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(
            download_configured_file(
                settings,
                canvas_file_id=args.file_id,
                canvas_course_id=args.course_id,
                force=args.force,
            )
        )
    except CanvasError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
