from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.canvas.exceptions import CanvasAPIError
from app.canvas.files import normalize_file
from app.database.file_repository import FileRepository
from app.database.models import CanvasFile, ModuleItem
from app.database.module_repository import ModuleRepository
from app.files.models import CanvasFileMetadata
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from app.services.file_metadata_sync import FileMetadataSyncService
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tests.factories import canvas_file_payload
from tests.services.test_assignment_sync import add_course


class FakeFileSource:
    def __init__(self, responses: dict[str, CanvasFileMetadata | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def fetch_file(self, canvas_file_id: str) -> CanvasFileMetadata:
        self.calls.append(canvas_file_id)
        response = self.responses[canvas_file_id]
        if isinstance(response, Exception):
            raise response
        return response


def add_file_module(
    session: Session,
    *,
    course_id: str,
    module_id: str,
    references: list[tuple[str, str]],
) -> None:
    course = add_course(session, course_id)
    items = tuple(
        ModuleItemSnapshot(
            canvas_module_item_id=item_id,
            canvas_module_id=module_id,
            canvas_course_id=course_id,
            title=f"File {file_id}",
            position=index,
            item_type="File",
            content_id=file_id,
        )
        for index, (item_id, file_id) in enumerate(references, start=1)
    )
    ModuleRepository(session).synchronize_course(
        course,
        [
            ModuleSnapshot(
                canvas_module_id=module_id,
                canvas_course_id=course_id,
                position=1,
                items=items,
            )
        ],
        synced_at=datetime(2026, 9, 28, tzinfo=UTC),
    )
    session.commit()


@pytest.mark.asyncio
async def test_metadata_sync_deduplicates_references_and_is_idempotent(session: Session) -> None:
    add_file_module(
        session,
        course_id="101",
        module_id="201",
        references=[("1001", "7001"), ("1002", "7001"), ("1003", "7002")],
    )
    source = FakeFileSource(
        {
            "7001": normalize_file(canvas_file_payload("7001")),
            "7002": normalize_file(canvas_file_payload("7002", filename="slides.pptx")),
        }
    )
    service = FileMetadataSyncService(
        source=source,
        session=session,
        clock=lambda: datetime(2026, 9, 29, tzinfo=UTC),
    )

    first = await service.synchronize()
    second = await service.synchronize()

    assert first.references_seen == 3
    assert first.unique_file_ids == 2
    assert first.files_created == 2
    assert second.files_created == 0
    assert second.files_unchanged == 2
    assert source.calls == ["7001", "7002", "7001", "7002"]
    assert len(session.scalars(select(CanvasFile)).all()) == 2


@pytest.mark.asyncio
async def test_same_file_across_courses_maps_to_one_record_with_multiple_provenance(
    session: Session,
) -> None:
    add_file_module(session, course_id="101", module_id="201", references=[("1001", "7001")])
    add_file_module(session, course_id="102", module_id="202", references=[("2001", "7001")])
    source = FakeFileSource({"7001": normalize_file(canvas_file_payload("7001"))})

    summary = await FileMetadataSyncService(source=source, session=session).synchronize()
    references = FileRepository(session).references_for(["7001"])["7001"]

    assert summary.references_seen == 2
    assert summary.unique_file_ids == 1
    assert source.calls == ["7001"]
    assert {reference.canvas_course_id for reference in references} == {"101", "102"}
    assert len(FileRepository(session).list_all()) == 1


@pytest.mark.asyncio
async def test_metadata_update_changes_existing_record_without_losing_identity(
    session: Session,
) -> None:
    add_file_module(session, course_id="101", module_id="201", references=[("1001", "7001")])
    source = FakeFileSource({"7001": normalize_file(canvas_file_payload())})
    service = FileMetadataSyncService(source=source, session=session)
    await service.synchronize()
    source.responses["7001"] = normalize_file(
        canvas_file_payload(filename="renamed.pdf", size=54321, updated_at="2026-09-29T12:00:00Z")
    )

    summary = await service.synchronize()
    record = FileRepository(session).get("7001")

    assert summary.files_updated == 1
    assert record is not None
    assert record.filename == "renamed.pdf"
    assert record.size == 54321
    assert len(FileRepository(session).list_all()) == 1


@pytest.mark.asyncio
async def test_inaccessible_or_transient_metadata_isolated_and_prior_data_preserved(
    session: Session,
) -> None:
    add_file_module(
        session,
        course_id="101",
        module_id="201",
        references=[("1001", "7001"), ("1002", "7002")],
    )
    initial = normalize_file(canvas_file_payload("7001"))
    FileRepository(session).synchronize(
        [initial.snapshot], synced_at=datetime(2026, 9, 28, tzinfo=UTC)
    )
    session.commit()
    source = FakeFileSource(
        {
            "7001": CanvasAPIError(
                "Canvas returned 503 with private upstream detail",
                status_code=503,
            ),
            "7002": normalize_file(canvas_file_payload("7002")),
        }
    )

    summary = await FileMetadataSyncService(source=source, session=session).synchronize()

    assert summary.metadata_succeeded == 1
    assert summary.metadata_failed == 1
    assert summary.files_created == 1
    assert FileRepository(session).get("7001").filename == "lecture-01.pdf"  # type: ignore[union-attr]
    assert "503" in summary.failures[0].message
    assert "private" not in summary.failures[0].message


@pytest.mark.asyncio
async def test_disappeared_reference_does_not_delete_file_metadata(session: Session) -> None:
    add_file_module(session, course_id="101", module_id="201", references=[("1001", "7001")])
    source = FakeFileSource({"7001": normalize_file(canvas_file_payload())})
    service = FileMetadataSyncService(source=source, session=session)
    await service.synchronize()
    session.execute(delete(ModuleItem))
    session.commit()

    summary = await service.synchronize()

    assert summary.references_seen == 0
    assert summary.unique_file_ids == 0
    assert FileRepository(session).get("7001") is not None
    assert FileRepository(session).course_owns_file("101", "7001") is False


@pytest.mark.asyncio
async def test_course_filter_limits_metadata_discovery_and_downloads_nothing(
    session: Session, tmp_path: Path
) -> None:
    add_file_module(session, course_id="101", module_id="201", references=[("1001", "7001")])
    add_file_module(session, course_id="102", module_id="202", references=[("2001", "7002")])
    source = FakeFileSource({"7001": normalize_file(canvas_file_payload("7001"))})

    summary = await FileMetadataSyncService(source=source, session=session).synchronize(
        canvas_course_id="101"
    )

    assert summary.references_seen == 1
    assert source.calls == ["7001"]
    assert not (tmp_path / "files").exists()
    assert "url" not in CanvasFile.__table__.columns
