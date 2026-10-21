"""Provider-neutral academic assistant API for local academic conversations."""

from __future__ import annotations

import json
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.assistant_stream_errors import format_assistant_stream_error
from app.assistant.blocking_runner import iter_orchestrator_events, run_orchestrator
from app.assistant_orchestration.models import AssistantEvent, AssistantEventType
from app.assistant_orchestration.service import AcademicAssistantOrchestrator, OrchestrationError
from app.assistant_provider.ollama import OllamaAcademicModelProvider, _normalize_base_url
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import AssistantRequest, AssistantResponse
from app.assistant_tools.service import AcademicToolService, LocalDocumentRetrievalProvider
from app.benchmarks.ollama import OllamaBenchmarkService
from app.canvas.exceptions import CanvasError
from app.config import get_settings
from app.course_router.models import CourseRoutingRequest, ResolutionOutcome
from app.database.session import get_session
from app.local_ai.service import LocalAISettingsService, resolve_installed_model_name
from app.services.assistant_material_preparation import AssistantMaterialPreparationService

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_TERMINAL_EVENT_TYPES = frozenset({AssistantEventType.COMPLETED, AssistantEventType.ERROR})


class DisconnectAwareCancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True


class AssistantStatusResponse(BaseModel):
    configured: bool
    provider: str
    available: bool | None = None
    selected_model: str | None = None
    selected_model_installed: bool | None = None


def _ollama_runtime_reachable(base_url: str, *, timeout_seconds: float = 3.0) -> bool:
    try:
        normalized = _normalize_base_url(base_url)
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(f"{normalized}/api/tags")
            return response.status_code == 200
    except (httpx.HTTPError, ValueError):
        return False


def get_model_provider(
    session: Annotated[Session, Depends(get_session)],
) -> Any:
    settings = get_settings()
    if settings.academic_model_provider == "ollama":
        selected = LocalAISettingsService(session, settings).selection()
        benchmark = OllamaBenchmarkService(settings)
        try:
            installed = benchmark.installed_models()
            model = resolve_installed_model_name(selected.model, installed)
        except (httpx.HTTPError, ValueError, RuntimeError):
            model = selected.model
        finally:
            benchmark.close()
        return OllamaAcademicModelProvider(model=model)
    return SyntheticAcademicModelProvider()


@router.get("/status", response_model=AssistantStatusResponse)
def status(
    session: Annotated[Session, Depends(get_session)],
) -> AssistantStatusResponse:
    settings = get_settings()
    if settings.academic_model_provider == "synthetic":
        return AssistantStatusResponse(
            configured=True,
            provider="synthetic",
            available=True,
        )
    try:
        _normalize_base_url(settings.ollama_base_url)
    except ValueError:
        return AssistantStatusResponse(
            configured=False,
            provider="ollama",
            available=False,
        )
    selection = LocalAISettingsService(session, settings).selection()
    benchmark = OllamaBenchmarkService(settings)
    try:
        installed = benchmark.installed_models()
    except (httpx.HTTPError, ValueError, RuntimeError):
        return AssistantStatusResponse(
            configured=True,
            provider="ollama",
            available=False,
            selected_model=selection.model,
            selected_model_installed=None,
        )
    finally:
        benchmark.close()
    resolved = resolve_installed_model_name(selection.model, installed)
    model_installed = resolved in installed
    return AssistantStatusResponse(
        configured=True,
        provider="ollama",
        available=model_installed,
        selected_model=resolved,
        selected_model_installed=model_installed,
    )


@router.post("/respond", response_model=AssistantResponse)
async def respond(
    request: AssistantRequest,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[Any, Depends(get_model_provider)],
) -> AssistantResponse:
    settings = get_settings()
    try:
        tools = AcademicToolService(session, academic_timezone=ZoneInfo(settings.academic_timezone))
        orchestrator = AcademicAssistantOrchestrator(
            tools,
            provider=provider,
            retrieval=LocalDocumentRetrievalProvider(tools),
        )
        await prepare_material_for_request(request, session, tools, orchestrator)
        return await run_orchestrator(orchestrator, request)
    except OrchestrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=format_assistant_stream_error(exc),
        ) from exc


@router.post("/stream")
async def stream(
    request: AssistantRequest,
    http_request: Request,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[Any, Depends(get_model_provider)],
) -> StreamingResponse:
    settings = get_settings()
    tools = AcademicToolService(session, academic_timezone=ZoneInfo(settings.academic_timezone))
    orchestrator = AcademicAssistantOrchestrator(
        tools,
        provider=provider,
        retrieval=LocalDocumentRetrievalProvider(tools),
    )
    await prepare_material_for_request(request, session, tools, orchestrator)
    token = DisconnectAwareCancellationToken()

    async def event_generator() -> Any:
        terminal_sent = False
        try:
            async for event in iter_orchestrator_events(
                orchestrator,
                request,
                cancellation=lambda: token.cancelled,
            ):
                if await http_request.is_disconnected():
                    token.cancel()
                    break
                if event.type in _TERMINAL_EVENT_TYPES:
                    terminal_sent = True
                yield self_describe(event, request)
            if await http_request.is_disconnected():
                yield self_describe(
                    AssistantEvent(
                        type="error",
                        text="client disconnected before completion",
                    ),
                    request,
                )
            elif not terminal_sent:
                yield self_describe(
                    AssistantEvent(
                        type="error",
                        text=format_assistant_stream_error(
                            RuntimeError("provider returned invalid stream data")
                        ),
                    ),
                    request,
                )
        except Exception as exc:
            token.cancel()
            yield self_describe(
                AssistantEvent(type="error", text=format_assistant_stream_error(exc)),
                request,
            )
        finally:
            token.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def prepare_material_for_request(
    request: AssistantRequest,
    session: Session,
    tools: AcademicToolService,
    orchestrator: AcademicAssistantOrchestrator,
) -> None:
    """Best-effort preparation before retrieval; failures keep existing safe behavior."""

    plan = orchestrator.plan(request)
    routing = tools.resolve_course(
        CourseRoutingRequest(
            course_id=request.course_id,
            assignment_id=request.assignment_id,
            document_id=request.document_id,
            active_course_id=request.active_course_id,
            text=request.query,
        )
    ).result
    if routing.outcome is not ResolutionOutcome.RESOLVED or routing.course is None:
        return
    try:
        await AssistantMaterialPreparationService(
            session=session,
            settings=get_settings(),
        ).prepare(
            request,
            operation=plan.operation,
            course_id=routing.course.course_id,
        )
    except (CanvasError, OSError, RuntimeError, SQLAlchemyError, ValueError):
        session.rollback()


def self_describe(event: AssistantEvent, request: AssistantRequest) -> str:
    payload: dict[str, Any] = {
        "type": event.type,
        "session_id": request.session_id,
        "course_id": request.course_id,
        "text": event.text,
        "block_type": event.block_type,
        "source": event.source,
        "identifier": event.identifier,
        "payload": event.payload,
        "references": [item.model_dump(mode="json") for item in event.references],
    }
    if event.response is not None:
        payload["response"] = event.response.model_dump(mode="json")
    return f"event: {event.type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
