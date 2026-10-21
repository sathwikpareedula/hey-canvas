"""Command-line entry point for the Phase 2 course-only synchronization."""

import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.client import CanvasClient
from app.canvas.courses import CanvasCourseSource
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.course_sync import CourseSyncService


async def synchronize_configured_courses(settings: Settings) -> int:
    """Synchronize only courses using credentials already configured locally."""

    base_url = settings.canvas_base_url
    token = resolve_canvas_token(settings)
    if base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before synchronizing courses"
        )

    initialize_database()
    async with CanvasClient(
        base_url=base_url,
        token=token,
    ) as client:
        with get_session_factory()() as session:
            summary = await CourseSyncService(
                source=CanvasCourseSource(client),
                session=session,
            ).synchronize()

    print("[OK] Canvas course synchronization completed.")
    print(f"Courses received:  {summary.courses_received}")
    print(f"Courses created:   {summary.courses_created}")
    print(f"Courses updated:   {summary.courses_updated}")
    print(f"Courses unchanged: {summary.courses_unchanged}")
    return 0


def run() -> int:
    """Run a safe course-only synchronization command."""

    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(synchronize_configured_courses(settings))
    except CanvasError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())

