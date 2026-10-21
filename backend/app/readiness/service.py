"""Safe readiness aggregation without credentials, paths, or network calls."""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import AcademicDocument, CanvasFile, SchemaVersion, SyncRun
from app.local_ai.service import LocalAISettingsService
from app.privacy.service import PrivacyService
from app.readiness.models import ReadinessComponent, ReadinessResponse
from app.security.canvas_credentials import canvas_configured


class ReadinessService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def check(self) -> ReadinessResponse:
        database = ReadinessComponent(status="ready")
        try:
            self._session.execute(text("SELECT 1"))
            schema_version = self._session.scalar(
                select(SchemaVersion.version).order_by(SchemaVersion.version.desc())
            )
            schema_state = ReadinessComponent(
                status="ready" if schema_version is not None else "degraded",
                detail=(
                    f"v{schema_version}"
                    if schema_version is not None
                    else "schema marker missing"
                ),
            )
        except Exception:
            database = ReadinessComponent(status="unavailable")
            schema_state = ReadinessComponent(status="unavailable")
        last_sync = self._session.scalar(
            select(SyncRun.finished_at)
            .where(SyncRun.status.in_(("succeeded", "partially_succeeded")))
            .order_by(SyncRun.finished_at.desc())
        )
        last_attempt = self._session.scalar(
            select(SyncRun.started_at).order_by(SyncRun.started_at.desc())
        )
        document_count = self._session.scalar(select(func.count(AcademicDocument.id))) or 0
        stale_count = self._session.scalar(
            select(func.count(AcademicDocument.id))
            .join(CanvasFile, CanvasFile.canvas_file_id == AcademicDocument.canvas_file_id)
            .where(
                AcademicDocument.source_sha256.is_not(None),
                CanvasFile.sha256.is_not(None),
                AcademicDocument.source_sha256 != CanvasFile.sha256,
            )
        ) or 0
        privacy = PrivacyService(self._session).settings()
        selected_model = LocalAISettingsService(self._session, self._settings).selection()
        return ReadinessResponse(
            backend=ReadinessComponent(status="ready"),
            database=database,
            schema=schema_state,
            canvas=ReadinessComponent(
                status="unknown" if canvas_configured(self._settings) else "not_configured",
                detail=(
                    "configured; live availability not checked"
                    if canvas_configured(self._settings)
                    else None
                ),
            ),
            last_sync=ReadinessComponent(
                status="ready" if last_sync is not None else "unknown",
                detail=last_sync.isoformat() if last_sync is not None else None,
            ),
            last_sync_attempt=ReadinessComponent(
                status="known" if last_attempt is not None else "unknown",
                detail=last_attempt.isoformat() if last_attempt is not None else None,
            ),
            documents=ReadinessComponent(
                status="ready" if document_count else "empty",
                detail=f"{document_count} indexed documents; {stale_count} stale",
            ),
            local_runtime=ReadinessComponent(status="configured", detail="provider-neutral"),
            local_model=ReadinessComponent(
                status="configured",
                detail=selected_model.model
                if self._settings.academic_model_provider == "ollama"
                else "synthetic",
            ),
            privacy=ReadinessComponent(status="ready", detail=privacy.mode.value),
        )
