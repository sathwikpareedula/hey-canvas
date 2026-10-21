"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.routes.academic_context import router as academic_context_router
from app.api.routes.assignments import router as assignments_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.automation import router as automation_router
from app.api.routes.benchmarks import router as benchmarks_router
from app.api.routes.calendar import router as calendar_router
from app.api.routes.canvas_operations import router as canvas_operations_router
from app.api.routes.changes import router as changes_router
from app.api.routes.course_profiles import router as course_profiles_router
from app.api.routes.course_router import router as course_router_router
from app.api.routes.courses import router as courses_router
from app.api.routes.deadlines import router as deadlines_router
from app.api.routes.documents import router as documents_router
from app.api.routes.files import router as files_router
from app.api.routes.focus_courses import router as focus_courses_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.lifecycle import router as lifecycle_router
from app.api.routes.local_ai import router as local_ai_router
from app.api.routes.modules import router as modules_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.privacy import router as privacy_router
from app.api.routes.readiness import router as readiness_router
from app.api.routes.reminders import router as reminders_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.security_health import router as security_health_router
from app.api.routes.storage import router as storage_router
from app.api.routes.study_context import router as study_context_router
from app.api.routes.study_guides import router as study_guides_router
from app.api.routes.study_sessions import router as study_sessions_router
from app.api.routes.sync_runs import router as sync_runs_router
from app.api.routes.workspaces import router as workspaces_router
from app.config import get_settings
from app.database.session import initialize_database
from app.logging import configure_logging
from app.security.canvas_credentials import bootstrap_credential_storage
from app.security.local_api_guard import LocalApiGuardMiddleware


class HealthResponse(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_database()
    bootstrap_credential_storage(settings)
    yield


app = FastAPI(
    title="UTA Academic Copilot",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(LocalApiGuardMiddleware)
app.include_router(courses_router)
app.include_router(course_profiles_router)
app.include_router(course_router_router)
app.include_router(calendar_router)
app.include_router(canvas_operations_router)
app.include_router(academic_context_router)
app.include_router(assistant_router)
app.include_router(automation_router)
app.include_router(study_context_router)
app.include_router(study_guides_router)
app.include_router(study_sessions_router)
app.include_router(assignments_router)
app.include_router(deadlines_router)
app.include_router(documents_router)
app.include_router(knowledge_router)
app.include_router(modules_router)
app.include_router(notifications_router)
app.include_router(reminders_router)
app.include_router(retrieval_router)
app.include_router(files_router)
app.include_router(focus_courses_router)
app.include_router(changes_router)
app.include_router(sync_runs_router)
app.include_router(workspaces_router)
app.include_router(privacy_router)
app.include_router(readiness_router)
app.include_router(lifecycle_router)
app.include_router(local_ai_router)
app.include_router(benchmarks_router)
app.include_router(security_health_router)
app.include_router(storage_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Return a credential-free process health response."""

    return HealthResponse(status="ok", service="uta-academic-copilot")
