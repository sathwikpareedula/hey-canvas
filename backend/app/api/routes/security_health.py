"""Security & Health Center API (credential-free)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.security.canvas_credential_store import save_canvas_token
from app.security.canvas_credentials import resolve_canvas_token
from app.security.health_center import SecurityHealthCenter
from app.security.models import SecurityHealthReport

router = APIRouter(prefix="/api/security", tags=["security"])


class SecurityHealthRunRequest(BaseModel):
    probe_canvas: bool = Field(default=True)
    probe_ollama: bool = Field(default=True)


class SecureStoreResult(BaseModel):
    stored: bool
    message: str


@router.get("/health", response_model=SecurityHealthReport)
def get_security_health(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SecurityHealthReport:
    """Snapshot checks without live network probes."""
    return SecurityHealthCenter(session, settings).run(probe_canvas=False, probe_ollama=False)


@router.post("/health/run", response_model=SecurityHealthReport)
def run_security_health(
    request: SecurityHealthRunRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SecurityHealthReport:
    """Run verified checks, optionally probing Canvas and Local AI."""
    return SecurityHealthCenter(session, settings).run(
        probe_canvas=request.probe_canvas,
        probe_ollama=request.probe_ollama,
    )


@router.post("/credentials/secure-store", response_model=SecureStoreResult)
def migrate_credentials_to_secure_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SecureStoreResult:
    """Copy configured env token into Windows DPAPI storage (never returns the token)."""
    token = resolve_canvas_token(settings)
    if settings.canvas_token is None and token is None:
        return SecureStoreResult(
            stored=False,
            message="No Canvas token is configured yet.",
        )
    env_token = settings.canvas_token or token
    if env_token is None:
        return SecureStoreResult(stored=False, message="No Canvas token is configured yet.")
    if save_canvas_token(env_token.get_secret_value()):
        return SecureStoreResult(
            stored=True,
            message="Canvas token encrypted for your Windows user account. "
            "You can remove CANVAS_TOKEN from .env when ready.",
        )
    return SecureStoreResult(
        stored=False,
        message="Secure storage is not available on this system. Keep using your local .env file.",
    )
