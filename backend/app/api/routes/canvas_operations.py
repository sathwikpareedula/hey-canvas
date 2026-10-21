"""Safe Canvas connectivity probe and read-only sync trigger."""

from __future__ import annotations

import asyncio
import threading
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.canvas.check import verify_canvas_connection
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasConfigurationError, CanvasError
from app.config import Settings, get_settings
from app.database.session import get_session
from app.security.canvas_credentials import canvas_configured, resolve_canvas_token
from app.sync.all_cli import synchronize_all

router = APIRouter(prefix="/api/canvas", tags=["canvas"])
_SYNC_SINGLE_FLIGHT = threading.Lock()


class CanvasConnectionResponse(BaseModel):
    status: Literal["ready", "not_configured", "unavailable"]
    detail: str | None = None


class CanvasSyncTriggerResponse(BaseModel):
    accepted: bool
    message: str
    run_id: int | None = None


def _probe_canvas(settings: Settings) -> CanvasConnectionResponse:
    if not canvas_configured(settings):
        return CanvasConnectionResponse(
            status="not_configured",
            detail="Canvas is not configured on this computer yet.",
        )
    token = resolve_canvas_token(settings)
    base_url = settings.canvas_base_url
    if token is None or not base_url:
        return CanvasConnectionResponse(
            status="not_configured",
            detail="Canvas credentials missing.",
        )

    async def _run() -> None:
        async with CanvasClient(base_url=base_url, token=token) as client:
            await verify_canvas_connection(client)

    try:
        asyncio.run(_run())
    except CanvasError:
        return CanvasConnectionResponse(
            status="unavailable",
            detail="Canvas could not be reached with your saved credentials.",
        )
    return CanvasConnectionResponse(status="ready", detail=None)


@router.get("/connection", response_model=CanvasConnectionResponse)
def canvas_connection(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CanvasConnectionResponse:
    return _probe_canvas(settings)


def _run_sync_job() -> None:
    settings = get_settings()
    try:
        asyncio.run(
            synchronize_all(
                settings,
                course_ids=[],
                check_local_files=False,
            )
        )
    except (CanvasError, CanvasConfigurationError, ValueError):
        return
    finally:
        _SYNC_SINGLE_FLIGHT.release()


@router.post("/sync", response_model=CanvasSyncTriggerResponse)
def trigger_canvas_sync(
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> CanvasSyncTriggerResponse:
    if not canvas_configured(settings):
        raise HTTPException(status_code=409, detail="Canvas is not configured on this computer.")
    if not _SYNC_SINGLE_FLIGHT.acquire(blocking=False):
        return CanvasSyncTriggerResponse(
            accepted=False,
            message="A Canvas sync is already running on this computer.",
            run_id=None,
        )
    from sqlalchemy import select

    from app.database.models import SyncRun

    running = session.scalar(
        select(SyncRun).where(SyncRun.status == "running").order_by(SyncRun.started_at.desc())
    )
    if running is not None:
        _SYNC_SINGLE_FLIGHT.release()
        return CanvasSyncTriggerResponse(
            accepted=False,
            message="A Canvas sync is already running on this computer.",
            run_id=running.id,
        )
    try:
        background_tasks.add_task(_run_sync_job)
    except Exception:
        _SYNC_SINGLE_FLIGHT.release()
        raise
    return CanvasSyncTriggerResponse(
        accepted=True,
        message="Canvas sync started. Refresh this page in a moment for progress.",
        run_id=None,
    )
