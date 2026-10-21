"""Local-only model selection API."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.benchmarks.ollama import OllamaBenchmarkService
from app.config import get_settings
from app.database.session import get_session
from app.local_ai.models import LocalModelSelection, LocalModelSelectionUpdate
from app.local_ai.service import LocalAISettingsService

router = APIRouter(prefix="/api/local-ai", tags=["local-ai"])


@router.get("/model", response_model=LocalModelSelection)
def get_local_model(
    session: Annotated[Session, Depends(get_session)],
) -> LocalModelSelection:
    return LocalAISettingsService(session, get_settings()).selection()


@router.put("/model", response_model=LocalModelSelection)
def select_local_model(
    request: LocalModelSelectionUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> LocalModelSelection:
    benchmark = OllamaBenchmarkService(get_settings())
    try:
        installed = benchmark.installed_models()
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Local AI runtime is unavailable.") from exc
    finally:
        benchmark.close()
    try:
        return LocalAISettingsService(session, get_settings()).select(
            request.model,
            installed_models=installed,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
