"""Bounded assistant-triggered preparation of authoritative Canvas materials."""

from __future__ import annotations

import re
from contextlib import AsyncExitStack
from typing import Protocol

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant_orchestration.models import AssistantOperation
from app.assistant_tools.models import AssistantRequest
from app.canvas.client import CanvasClient
from app.canvas.files import CanvasFileSource
from app.config import Settings
from app.database.file_repository import FileRepository
from app.database.models import CanvasFile, Course, CourseModule, ModuleItem
from app.documents.config import document_limits
from app.documents.models import IngestionOutcome
from app.documents.parsing import supported_candidate
from app.files.downloader import ControlledFileDownloader
from app.privacy.models import CourseAIPolicyValue
from app.privacy.service import PrivacyService
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_search import DocumentSearchService
from app.services.file_download import FileDownloadService

TOKEN = re.compile(r"[\w'-]+", re.UNICODE)
PREPARATION_OPERATIONS = frozenset(
    {
        AssistantOperation.MATERIAL_SEARCH,
        AssistantOperation.ASSIGNMENT_CONTEXT,
        AssistantOperation.STUDY_HELP,
        AssistantOperation.STUDY_PLAN,
        AssistantOperation.PRACTICE_SESSION,
        AssistantOperation.STUDY_GUIDE,
    }
)


class MaterialIngestor(Protocol):
    async def ingest_file(
        self,
        canvas_file_id: str,
        *,
        canvas_course_id: str | None = None,
        allow_download: bool = False,
    ) -> IngestionOutcome: ...


class MaterialPreparationResult(BaseModel):
    """Internal safe result; it deliberately contains no URLs, paths, or source text."""

    model_config = ConfigDict(frozen=True)

    status: str
    canvas_file_id: str | None = None
    ingestion_status: str | None = None


class AssistantMaterialPreparationService:
    """Prepare at most one deterministically relevant file before local retrieval.

    CourseMaterialReference is the authorization boundary. Generic course requests do
    not trigger a bulk download: an explicit document or an exact normalized title
    match to an authoritative Canvas module item is required.
    """

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        ingestor: MaterialIngestor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._ingestor = ingestor

    async def prepare(
        self,
        request: AssistantRequest,
        *,
        operation: AssistantOperation,
        course_id: str | None,
    ) -> MaterialPreparationResult:
        if operation not in PREPARATION_OPERATIONS or course_id is None:
            return MaterialPreparationResult(status="not_applicable")
        if PrivacyService(self._session).policy(course_id).policy is CourseAIPolicyValue.DISABLED:
            return MaterialPreparationResult(status="policy_disabled")
        if self._has_current_evidence(request, course_id):
            return MaterialPreparationResult(status="already_indexed")

        candidate = self._candidate(request, course_id)
        if candidate is None:
            return MaterialPreparationResult(status="no_unambiguous_material")
        outcome = await self._ingest(candidate.canvas_file_id, course_id)
        status = "prepared" if outcome.parsed or outcome.skipped else "unavailable"
        return MaterialPreparationResult(
            status=status,
            canvas_file_id=candidate.canvas_file_id,
            ingestion_status=outcome.status,
        )

    def _has_current_evidence(self, request: AssistantRequest, course_id: str) -> bool:
        hits = DocumentSearchService(self._session).search(
            request.query,
            canvas_course_id=course_id,
            canvas_file_id=request.document_id,
            limit=1,
        )
        return any(not hit.is_stale for hit in hits)

    def _candidate(self, request: AssistantRequest, course_id: str) -> CanvasFile | None:
        repository = FileRepository(self._session)
        records = repository.list_all(
            canvas_course_id=course_id,
            canvas_file_id=request.document_id,
        )
        candidates = {
            record.canvas_file_id: record for record in records if self._eligible(record)
        }
        if request.document_id is not None:
            return candidates.get(request.document_id)

        if request.assignment_id is not None:
            module_ids = set(
                self._session.scalars(
                    select(CourseModule.canvas_module_id)
                    .join(Course, CourseModule.course_id == Course.id)
                    .join(ModuleItem, ModuleItem.module_id == CourseModule.id)
                    .where(
                        Course.canvas_course_id == course_id,
                        ModuleItem.item_type == "Assignment",
                        ModuleItem.content_id == request.assignment_id,
                    )
                )
            )
            if not module_ids:
                return None
            references = repository.references_for(candidates)
            related = [
                record
                for file_id, record in candidates.items()
                if any(
                    reference.canvas_course_id == course_id
                    and reference.canvas_module_id in module_ids
                    for reference in references.get(file_id, ())
                )
            ]
            if len(related) == 1:
                return related[0]
            candidates = {record.canvas_file_id: record for record in related}

        normalized_query = " ".join(TOKEN.findall(request.query.casefold()))
        references = repository.references_for(candidates)
        matched = [
            record
            for file_id, record in candidates.items()
            if any(
                reference.canvas_course_id == course_id
                and reference.item_title
                and f" {' '.join(TOKEN.findall(reference.item_title.casefold()))} "
                in f" {normalized_query} "
                for reference in references.get(file_id, ())
            )
        ]
        if len(matched) != 1:
            return None
        return matched[0]

    def _eligible(self, record: CanvasFile) -> bool:
        if record.locked is True or record.hidden is True or record.hidden_for_user is True:
            return False
        if not supported_candidate(record.filename or record.display_name, record.content_type):
            return False
        size = record.size if record.size is not None else record.local_size
        return size is not None and 0 <= size <= self._settings.max_canvas_file_bytes

    async def _ingest(self, canvas_file_id: str, course_id: str) -> IngestionOutcome:
        if self._ingestor is not None:
            return await self._ingestor.ingest_file(
                canvas_file_id,
                canvas_course_id=course_id,
                allow_download=True,
            )

        async with AsyncExitStack() as stack:
            downloader_service: FileDownloadService | None = None
            from app.security.canvas_credentials import resolve_canvas_token

            token = resolve_canvas_token(self._settings)
            if self._settings.canvas_base_url and token:
                client = await stack.enter_async_context(
                    CanvasClient(
                        base_url=self._settings.canvas_base_url,
                        token=token,
                    )
                )
                binary_downloader = await stack.enter_async_context(
                    ControlledFileDownloader(
                        canvas_base_url=self._settings.canvas_base_url,
                        token=token,
                        max_bytes=self._settings.max_canvas_file_bytes,
                    )
                )
                downloader_service = FileDownloadService(
                    source=CanvasFileSource(client),
                    downloader=binary_downloader,
                    session=self._session,
                    storage_root=self._settings.academic_files_root,
                )
            ingestion = DocumentIngestionService(
                session=self._session,
                storage_root=self._settings.academic_files_root,
                limits=document_limits(self._settings),
                downloader=downloader_service,
            )
            return await ingestion.ingest_file(
                canvas_file_id,
                canvas_course_id=course_id,
                allow_download=True,
            )
