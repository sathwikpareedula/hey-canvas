from pathlib import Path

import pytest
from app.assistant_orchestration.models import AssistantOperation
from app.assistant_tools.models import AssistantRequest
from app.config import Settings
from app.database.module_repository import ModuleRepository
from app.documents.models import DocumentLimits, IngestionOutcome
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from app.services.assistant_material_preparation import (
    AssistantMaterialPreparationService,
)
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_search import DocumentSearchService
from sqlalchemy.orm import Session

from tests.services.test_assignment_sync import add_course
from tests.test_document_ingestion import NOW, seed_metadata, seed_references, store_local
from tests.test_document_ingestion import (
    limits as document_limits_fixture,
)

# Make pytest retain the imported fixture under an explicit local name.
limits = document_limits_fixture


class RecordingIngestor:
    def __init__(self, outcome: IngestionOutcome) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str | None, bool]] = []

    async def ingest_file(
        self,
        canvas_file_id: str,
        *,
        canvas_course_id: str | None = None,
        allow_download: bool = False,
    ) -> IngestionOutcome:
        self.calls.append((canvas_file_id, canvas_course_id, allow_download))
        return self.outcome


def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        academic_files_root=tmp_path,
        canvas_base_url=None,
        canvas_token=None,
        max_canvas_file_bytes=1_000_000,
    )


@pytest.mark.asyncio
async def test_known_explicit_material_is_prepared_once(
    session: Session, tmp_path: Path
) -> None:
    seed_references(
        session,
        references=[("item-1", "file-1", "Lecture 6")],
    )
    seed_metadata(session, file_id="file-1", filename="lecture-6.txt", body_size=20)
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="file-1", status="parsed", parsed=True, units=1)
    )
    service = AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    )

    result = await service.prepare(
        AssistantRequest(
            query="Explain this lecture.",
            course_id="101",
            document_id="file-1",
        ),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )

    assert result.status == "prepared"
    assert ingestor.calls == [("file-1", "101", True)]


@pytest.mark.asyncio
async def test_successful_preparation_immediately_enables_local_retrieval(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
) -> None:
    body = b"forward kinematics maps joint angles into tool position"
    seed_references(
        session,
        references=[("item-1", "file-1", "Lecture 6")],
    )
    seed_metadata(
        session,
        file_id="file-1",
        filename="lecture-6.txt",
        body_size=len(body),
    )

    class PreparingIngestor:
        calls = 0

        async def ingest_file(
            self,
            canvas_file_id: str,
            *,
            canvas_course_id: str | None = None,
            allow_download: bool = False,
        ) -> IngestionOutcome:
            self.calls += 1
            store_local(session, tmp_path, canvas_file_id, "lecture-6.txt", body)
            return await DocumentIngestionService(
                session=session,
                storage_root=tmp_path,
                limits=limits,
            ).ingest_file(canvas_file_id, canvas_course_id=canvas_course_id)

    ingestor = PreparingIngestor()
    service = AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    )
    request = AssistantRequest(
        query="forward kinematics",
        course_id="101",
        document_id="file-1",
    )

    first = await service.prepare(
        request,
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )
    second = await service.prepare(
        request,
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )

    assert first.status == "prepared"
    assert second.status == "already_indexed"
    assert ingestor.calls == 1
    hits = DocumentSearchService(session).search(
        "forward kinematics", canvas_course_id="101"
    )
    assert [hit.canvas_file_id for hit in hits] == ["file-1"]


@pytest.mark.asyncio
async def test_assignment_context_prepares_one_authoritatively_linked_module_file(
    session: Session, tmp_path: Path
) -> None:
    course = add_course(session, "101")
    ModuleRepository(session).synchronize_course(
        course,
        [
            ModuleSnapshot(
                canvas_module_id="module-1",
                canvas_course_id="101",
                name="Project work",
                items=(
                    ModuleItemSnapshot(
                        canvas_module_item_id="assignment-item",
                        canvas_module_id="module-1",
                        canvas_course_id="101",
                        title="Individual report",
                        item_type="Assignment",
                        content_id="assignment-1",
                    ),
                    ModuleItemSnapshot(
                        canvas_module_item_id="file-item",
                        canvas_module_id="module-1",
                        canvas_course_id="101",
                        title="Individual report instructions",
                        item_type="File",
                        content_id="file-1",
                    ),
                ),
            )
        ],
        synced_at=NOW,
    )
    session.commit()
    seed_metadata(session, file_id="file-1", filename="instructions.txt", body_size=20)
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="file-1", status="parsed", parsed=True, units=1)
    )

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(
            query="How do I do the individual report?",
            course_id="101",
            assignment_id="assignment-1",
        ),
        operation=AssistantOperation.ASSIGNMENT_CONTEXT,
        course_id="101",
    )

    assert result.status == "prepared"
    assert ingestor.calls == [("file-1", "101", True)]


@pytest.mark.asyncio
async def test_preparation_failure_is_bounded_and_leaves_no_evidence(
    session: Session, tmp_path: Path
) -> None:
    seed_references(session, references=[("item-1", "file-1", "Lecture 6")])
    seed_metadata(session, file_id="file-1", filename="lecture-6.txt", body_size=20)
    ingestor = RecordingIngestor(
        IngestionOutcome(
            canvas_file_id="file-1",
            status="failed",
            error_category="download_failed",
        )
    )
    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(query="Lecture 6", course_id="101", document_id="file-1"),
        operation=AssistantOperation.STUDY_HELP,
        course_id="101",
    )

    assert result.model_dump() == {
        "status": "unavailable",
        "canvas_file_id": "file-1",
        "ingestion_status": "failed",
    }
    assert DocumentSearchService(session).search("Lecture 6", canvas_course_id="101") == []


@pytest.mark.asyncio
async def test_offline_missing_material_does_not_attempt_a_network_client(
    session: Session, tmp_path: Path
) -> None:
    seed_references(session, references=[("item-1", "file-1", "Lecture 6")])
    seed_metadata(session, file_id="file-1", filename="lecture-6.txt", body_size=20)

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
    ).prepare(
        AssistantRequest(query="Lecture 6", course_id="101", document_id="file-1"),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )

    assert result.status == "unavailable"
    assert result.ingestion_status == "download_required"


@pytest.mark.asyncio
async def test_wrong_course_document_is_never_prepared(
    session: Session, tmp_path: Path
) -> None:
    seed_references(session, references=[("item-1", "file-1", "Lecture 6")])
    seed_metadata(session, file_id="file-1", filename="lecture-6.txt", body_size=20)
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="file-1", status="parsed", parsed=True)
    )

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(query="Lecture 6", course_id="other", document_id="file-1"),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="other",
    )

    assert result.status == "no_unambiguous_material"
    assert ingestor.calls == []


@pytest.mark.asyncio
async def test_title_matching_uses_exact_authoritative_module_item_not_filename_similarity(
    session: Session, tmp_path: Path
) -> None:
    seed_references(
        session,
        references=[
            ("item-1", "file-1", "Lecture 6"),
            ("item-2", "file-2", "Lecture 7"),
        ],
    )
    seed_metadata(session, file_id="file-1", filename="robotics-notes.txt", body_size=20)
    seed_metadata(session, file_id="file-2", filename="lecture-6-copy.txt", body_size=20)
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="file-1", status="parsed", parsed=True)
    )

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(query="Explain Lecture 6 for me", course_id="101"),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )

    assert result.canvas_file_id == "file-1"
    assert ingestor.calls == [("file-1", "101", True)]


@pytest.mark.asyncio
async def test_shared_file_preparation_stays_with_explicit_course(
    session: Session, tmp_path: Path
) -> None:
    seed_references(
        session,
        course_id="101",
        module_id="201",
        references=[("item-1", "shared", "Shared Lecture")],
    )
    seed_references(
        session,
        course_id="202",
        module_id="202-module",
        references=[("item-2", "shared", "Shared Lecture")],
    )
    seed_metadata(session, file_id="shared", filename="shared.txt", body_size=20)
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="shared", status="parsed", parsed=True)
    )

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(query="Shared Lecture", course_id="202", document_id="shared"),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="202",
    )

    assert result.status == "prepared"
    assert ingestor.calls == [("shared", "202", True)]


@pytest.mark.asyncio
async def test_stale_index_is_reprepared_instead_of_treated_as_current(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
) -> None:
    original = b"forward kinematics lecture"
    seed_references(session, references=[("item-1", "file-1", "Lecture 6")])
    seed_metadata(
        session,
        file_id="file-1",
        filename="lecture-6.txt",
        body_size=len(original),
    )
    store_local(session, tmp_path, "file-1", "lecture-6.txt", original)
    await DocumentIngestionService(
        session=session,
        storage_root=tmp_path,
        limits=limits,
    ).ingest_file("file-1", canvas_course_id="101")
    store_local(
        session,
        tmp_path,
        "file-1",
        "lecture-6.txt",
        b"updated forward kinematics lecture",
    )
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="file-1", status="parsed", parsed=True)
    )

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(
            query="forward kinematics",
            course_id="101",
            document_id="file-1",
        ),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )

    assert result.status == "prepared"
    assert ingestor.calls == [("file-1", "101", True)]


@pytest.mark.asyncio
async def test_canvas_metadata_change_marks_old_index_stale_and_reprepares(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
) -> None:
    body = b"original lecture material"
    seed_references(session, references=[("item-1", "file-1", "Lecture 6")])
    seed_metadata(session, file_id="file-1", filename="lecture-6.txt", body_size=len(body))
    store_local(session, tmp_path, "file-1", "lecture-6.txt", body)
    await DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits
    ).ingest_file("file-1", canvas_course_id="101")
    seed_metadata(
        session,
        file_id="file-1",
        filename="lecture-6-revised.txt",
        body_size=len(body),
    )
    assert DocumentSearchService(session).search(
        "original lecture", canvas_course_id="101"
    )[0].is_stale is True
    ingestor = RecordingIngestor(
        IngestionOutcome(canvas_file_id="file-1", status="parsed", parsed=True)
    )

    result = await AssistantMaterialPreparationService(
        session=session,
        settings=settings(tmp_path),
        ingestor=ingestor,
    ).prepare(
        AssistantRequest(
            query="original lecture",
            course_id="101",
            document_id="file-1",
        ),
        operation=AssistantOperation.MATERIAL_SEARCH,
        course_id="101",
    )

    assert result.status == "prepared"
    assert ingestor.calls == [("file-1", "101", True)]
