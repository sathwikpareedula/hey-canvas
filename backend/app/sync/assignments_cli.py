"""Command-line entry point for assignment-only synchronization."""

import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.assignments import CanvasAssignmentSource
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.assignment_sync import AssignmentSyncService


async def synchronize_configured_assignments(settings: Settings) -> int:
    """Synchronize assignment metadata for locally known active courses only."""

    base_url = settings.canvas_base_url
    token = resolve_canvas_token(settings)
    if base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before synchronizing assignments"
        )

    initialize_database()
    async with CanvasClient(
        base_url=base_url,
        token=token,
    ) as client:
        with get_session_factory()() as session:
            summary = await AssignmentSyncService(
                source=CanvasAssignmentSource(client),
                session=session,
            ).synchronize()

    if summary.courses_attempted == 0:
        print("[OK] No active local courses were found. Run canvas-sync-courses first.")
        return 0

    print("[OK] Canvas assignment synchronization completed.")
    print(f"Courses attempted:     {summary.courses_attempted}")
    print(f"Courses succeeded:     {summary.courses_succeeded}")
    print(f"Courses failed:        {summary.courses_failed}")
    print(f"Assignments received:  {summary.assignments_received}")
    print(f"Assignments created:   {summary.assignments_created}")
    print(f"Assignments updated:   {summary.assignments_updated}")
    print(f"Assignments unchanged: {summary.assignments_unchanged}")
    for failure in summary.failures:
        print(
            f"[FAILED] Course {failure.canvas_course_id}: {failure.error_type} - {failure.message}",
            file=sys.stderr,
        )
    return 1 if summary.courses_failed else 0


def run() -> int:
    """Run the safe assignment-only synchronization command."""

    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(synchronize_configured_assignments(settings))
    except CanvasError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())

