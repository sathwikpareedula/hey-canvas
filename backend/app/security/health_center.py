"""Verified security & health checks (no secrets in output)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes import assistant as assistant_routes
from app.config import Settings
from app.database.models import AcademicDocument, CanvasFile, SyncRun
from app.readiness.service import ReadinessService
from app.security.canvas_credential_store import store_status
from app.security.canvas_credentials import (
    canvas_configured,
    credential_protection_summary,
    env_file_lists_canvas_token,
)
from app.security.models import SecurityCheck, SecurityCheckStatus, SecurityHealthReport


def _overall(checks: list[SecurityCheck]) -> str:
    if any(c.status == SecurityCheckStatus.FAIL for c in checks):
        return "fail"
    if any(c.status == SecurityCheckStatus.WARNING for c in checks):
        return "warning"
    if all(c.status == SecurityCheckStatus.PASS for c in checks):
        return "pass"
    if any(c.status == SecurityCheckStatus.NOT_CHECKED for c in checks):
        return "not_checked"
    return "warning"


class SecurityHealthCenter:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def run(
        self,
        *,
        probe_canvas: bool = False,
        probe_ollama: bool = False,
    ) -> SecurityHealthReport:
        checks = [
            self._check_canvas_connection(probe_live=probe_canvas),
            self._check_credential_protection(),
            self._check_local_exposure(),
            self._check_local_ai(probe_live=probe_ollama),
            self._check_sync_freshness(),
            self._check_materials(),
            self._check_configuration_risks(),
        ]
        return SecurityHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            checks=checks,
            overall=_overall(checks),
        )

    def _check_canvas_connection(self, *, probe_live: bool) -> SecurityCheck:
        if not canvas_configured(self._settings):
            return SecurityCheck(
                id="canvas_connection",
                title="Canvas connection",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Canvas is not configured on this computer yet.",
            )
        if not probe_live:
            return SecurityCheck(
                id="canvas_connection",
                title="Canvas connection",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Canvas credentials are present. Run checks to verify live access.",
            )
        try:
            import asyncio

            from app.canvas.check import verify_canvas_connection
            from app.canvas.client import CanvasClient
            from app.security.canvas_credentials import resolve_canvas_token

            token = resolve_canvas_token(self._settings)
            base_url = self._settings.canvas_base_url
            if token is None or not base_url:
                raise ValueError("missing")

            async def _probe() -> None:
                async with CanvasClient(
                    base_url=base_url,
                    token=token,
                ) as client:
                    await verify_canvas_connection(client)

            asyncio.run(_probe())
        except Exception:
            return SecurityCheck(
                id="canvas_connection",
                title="Canvas connection",
                status=SecurityCheckStatus.FAIL,
                summary="Hey Canvas could not reach Canvas with your saved credentials.",
                detail=(
                    "Check that your token is still valid and that you can open "
                    "Canvas in a browser."
                ),
            )
        return SecurityCheck(
            id="canvas_connection",
            title="Canvas connection",
            status=SecurityCheckStatus.PASS,
            summary="Canvas accepted your credentials (read-only check).",
        )

    def _check_credential_protection(self) -> SecurityCheck:
        level, message = credential_protection_summary(self._settings)
        status = {
            "pass": SecurityCheckStatus.PASS,
            "warning": SecurityCheckStatus.WARNING,
            "not_checked": SecurityCheckStatus.NOT_CHECKED,
        }[level]
        store = store_status()
        detail = None
        if store.has_token:
            detail = (
                "Windows secure storage contains an encrypted Canvas token "
                "for your user account."
            )
        elif env_file_lists_canvas_token():
            detail = "A Canvas token entry was found in your local environment file."
        return SecurityCheck(
            id="credential_protection",
            title="Credential protection",
            status=status,
            summary=message,
            detail=detail,
        )

    def _check_local_exposure(self) -> SecurityCheck:
        host = self._settings.api_bind_host.strip().lower()
        remote = self._settings.api_allow_remote_bind
        if remote:
            return SecurityCheck(
                id="local_service_exposure",
                title="Local service exposure",
                status=SecurityCheckStatus.FAIL,
                summary="The academic API is configured to accept remote network connections.",
                detail=(
                    "Use loopback binding (127.0.0.1) unless you intentionally "
                    "share this computer."
                ),
            )
        if host not in {"127.0.0.1", "localhost"}:
            return SecurityCheck(
                id="local_service_exposure",
                title="Local service exposure",
                status=SecurityCheckStatus.WARNING,
                summary=f"The API bind host is set to {host}.",
                detail="Hey Canvas expects local-only access on your computer.",
            )
        return SecurityCheck(
            id="local_service_exposure",
            title="Local service exposure",
            status=SecurityCheckStatus.PASS,
            summary="The academic API is intended for this computer only (loopback).",
        )

    def _check_local_ai(self, *, probe_live: bool) -> SecurityCheck:
        if self._settings.academic_model_provider == "synthetic":
            return SecurityCheck(
                id="local_ai",
                title="Local AI",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Local AI is in demo/synthetic mode.",
            )
        if not probe_live:
            return SecurityCheck(
                id="local_ai",
                title="Local AI",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Run checks to probe Ollama on this computer.",
            )
        reachable = assistant_routes._ollama_runtime_reachable(self._settings.ollama_base_url)
        if reachable:
            return SecurityCheck(
                id="local_ai",
                title="Local AI",
                status=SecurityCheckStatus.PASS,
                summary="Your local AI runtime responded on this computer.",
            )
        return SecurityCheck(
            id="local_ai",
            title="Local AI",
            status=SecurityCheckStatus.WARNING,
            summary="Local AI is not reachable right now.",
            detail="Start Ollama or open Settings → Local AI for setup steps.",
        )

    def _check_sync_freshness(self) -> SecurityCheck:
        try:
            last = self._session.scalar(
            select(SyncRun.finished_at)
            .where(SyncRun.status.in_(("succeeded", "partially_succeeded")))
            .order_by(SyncRun.finished_at.desc())
            )
        except Exception:
            return SecurityCheck(
                id="sync_freshness",
                title="Academic sync",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Sync history is not available yet on this database.",
            )
        if last is None:
            return SecurityCheck(
                id="sync_freshness",
                title="Academic sync",
                status=SecurityCheckStatus.WARNING,
                summary="No successful Canvas sync has finished yet.",
            )
        age = datetime.now(UTC) - last.replace(tzinfo=UTC)
        if age > timedelta(days=7):
            return SecurityCheck(
                id="sync_freshness",
                title="Academic sync",
                status=SecurityCheckStatus.WARNING,
                summary="Your last successful sync was more than a week ago.",
                detail="Run sync from Settings if deadlines or materials look stale.",
            )
        return SecurityCheck(
            id="sync_freshness",
            title="Academic sync",
            status=SecurityCheckStatus.PASS,
            summary="Canvas data was synced recently on this computer.",
        )

    def _check_materials(self) -> SecurityCheck:
        try:
            readiness = ReadinessService(self._session, self._settings).check()
        except Exception:
            return SecurityCheck(
                id="materials_health",
                title="Course materials",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Material index is not available yet on this database.",
            )
        doc_detail = readiness.documents.detail or ""
        try:
            stale_count = self._session.scalar(
            select(func.count(AcademicDocument.id))
            .join(CanvasFile, CanvasFile.canvas_file_id == AcademicDocument.canvas_file_id)
            .where(
                AcademicDocument.source_sha256.is_not(None),
                CanvasFile.sha256.is_not(None),
                AcademicDocument.source_sha256 != CanvasFile.sha256,
            )
            ) or 0
        except Exception:
            return SecurityCheck(
                id="materials_health",
                title="Course materials",
                status=SecurityCheckStatus.NOT_CHECKED,
                summary="Material index is not available yet on this database.",
            )
        if readiness.documents.status == "empty":
            return SecurityCheck(
                id="materials_health",
                title="Course materials",
                status=SecurityCheckStatus.WARNING,
                summary="No indexed course materials yet.",
                detail="Sync and ingest PDFs to power citations.",
            )
        if stale_count > 0:
            return SecurityCheck(
                id="materials_health",
                title="Course materials",
                status=SecurityCheckStatus.WARNING,
                summary=f"{stale_count} material(s) may be out of date with Canvas.",
                detail=doc_detail,
            )
        return SecurityCheck(
            id="materials_health",
            title="Course materials",
            status=SecurityCheckStatus.PASS,
            summary="Indexed materials look consistent with your local library.",
            detail=doc_detail,
        )

    def _check_configuration_risks(self) -> SecurityCheck:
        risks: list[str] = []
        if self._settings.local_api_guard_enabled is False:
            risks.append("Local API origin checks are turned off.")
        if self._settings.app_env == "development" and env_file_lists_canvas_token():
            risks.append("Development mode with a plaintext Canvas token in .env.")
        if not risks:
            return SecurityCheck(
                id="configuration_risks",
                title="Configuration risks",
                status=SecurityCheckStatus.PASS,
                summary="No obvious local configuration risks were detected.",
            )
        return SecurityCheck(
            id="configuration_risks",
            title="Configuration risks",
            status=SecurityCheckStatus.WARNING,
            summary="Some settings could be tightened for everyday use.",
            detail=" ".join(risks),
        )
