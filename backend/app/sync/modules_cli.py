"""Command-line entry point for module-only synchronization."""

import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.canvas.modules import CanvasModuleSource
from app.config import Settings, get_settings
from app.database.session import get_session_factory, initialize_database
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token
from app.services.module_sync import ModuleSyncService


async def synchronize_configured_modules(settings: Settings) -> int:
    """Synchronize module metadata and inert item references for known courses."""

    base_url = settings.canvas_base_url
    token = resolve_canvas_token(settings)
    if base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before synchronizing modules"
        )

    initialize_database()
    async with CanvasClient(
        base_url=base_url,
        token=token,
    ) as client:
        with get_session_factory()() as session:
            summary = await ModuleSyncService(
                source=CanvasModuleSource(client),
                session=session,
            ).synchronize()

    if summary.courses_attempted == 0:
        print("[OK] No active local courses were found. Run canvas-sync-courses first.")
        return 0

    print("[OK] Canvas module synchronization completed.")
    for label, value in (
        ("Courses attempted", summary.courses_attempted),
        ("Courses succeeded", summary.courses_succeeded),
        ("Courses failed", summary.courses_failed),
        ("Modules received", summary.modules_received),
        ("Modules created", summary.modules_created),
        ("Modules updated", summary.modules_updated),
        ("Modules unchanged", summary.modules_unchanged),
        ("Items received", summary.items_received),
        ("Items created", summary.items_created),
        ("Items updated", summary.items_updated),
        ("Items unchanged", summary.items_unchanged),
    ):
        print(f"{label + ':':20} {value}")
    for failure in summary.failures:
        print(
            f"[FAILED] Course {failure.canvas_course_id}: "
            f"{failure.error_type} - {failure.message}",
            file=sys.stderr,
        )
    return 1 if summary.courses_failed else 0


def run() -> int:
    """Run the safe module-only synchronization command."""

    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        return asyncio.run(synchronize_configured_modules(settings))
    except CanvasError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("[ERROR] Local database operation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
