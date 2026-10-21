import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.canvas.exceptions import CanvasAPIError
from app.database.document_repository import DocumentRepository
from app.database.file_repository import FileRepository
from app.database.models import AcademicDocument, DocumentUnit
from app.database.module_repository import ModuleRepository
from app.documents.models import DocumentLimits
from app.documents.parsing import PARSER_VERSION, DocumentParseError
from app.files.models import FileDownloadSummary, FileSnapshot
from app.files.paths import destination_for, relative_storage_path
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from app.services.document_ingestion import DocumentIngestionService
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.services.test_assignment_sync import add_course

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


@pytest.fixture
def limits() -> DocumentLimits:
    return DocumentLimits(
        max_source_bytes=5_000_000,
        max_characters=10_000,
        max_units=100,
        max_unit_characters=2_000,
        max_archive_entries=200,
        max_archive_uncompressed_bytes=5_000_000,
        max_archive_ratio=200,
    )


def seed_references(
    session: Session,
    *,
    course_id: str = "101",
    module_id: str = "201",
    references: list[tuple[str, str, str]],
) -> None:
    course = add_course(session, course_id)
    ModuleRepository(session).synchronize_course(
        course,
        [
            ModuleSnapshot(
                canvas_module_id=module_id,
                canvas_course_id=course_id,
                name="Lectures",
                items=tuple(
                    ModuleItemSnapshot(
                        canvas_module_item_id=item_id,
                        canvas_module_id=module_id,
                        canvas_course_id=course_id,
                        item_type="File",
                        content_id=file_id,
                        title=title,
                    )
                    for item_id, file_id, title in references
                ),
            )
        ],
        synced_at=NOW,
    )
    session.commit()


def seed_metadata(
    session: Session,
    *,
    file_id: str,
    filename: str,
    body_size: int,
    content_type: str = "text/plain",
) -> None:
    FileRepository(session).synchronize(
        [
            FileSnapshot(
                canvas_file_id=file_id,
                display_name=filename,
                filename=filename,
                content_type=content_type,
                size=body_size,
            )
        ],
        synced_at=NOW,
    )
    session.commit()


def store_local(session: Session, root: Path, file_id: str, filename: str, body: bytes) -> None:
    path = destination_for(root, canvas_file_id=file_id, filename=filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    record = FileRepository(session).get(file_id)
    assert record is not None
    FileRepository(session).record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path=relative_storage_path(root, path),
        sha256=hashlib.sha256(body).hexdigest(),
        local_size=len(body),
        http_content_type=record.content_type,
    )
    session.commit()


def seed_local_text(
    session: Session,
    root: Path,
    *,
    file_id: str = "7001",
    filename: str = "lecture.txt",
    body: bytes = b"inverse kinematics and robot control",
    duplicate_reference: bool = False,
) -> None:
    refs = [("1001", file_id, filename)]
    if duplicate_reference:
        refs.append(("1002", file_id, f"Copy of {filename}"))
    seed_references(session, references=refs)
    seed_metadata(session, file_id=file_id, filename=filename, body_size=len(body))
    store_local(session, root, file_id, filename, body)


@pytest.mark.asyncio
async def test_one_file_one_document_multiple_references_and_cache_skip(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_local_text(session, tmp_path, duplicate_reference=True)
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    first = await service.ingest_file("7001")
    second = await service.ingest_file("7001")
    assert first.parsed is True
    assert second.skipped is True
    assert session.scalar(select(func.count()).select_from(AcademicDocument)) == 1
    assert session.scalar(select(func.count()).select_from(DocumentUnit)) == 1
    record = FileRepository(session).get("7001")
    assert record is not None and record.sha256
    repository = DocumentRepository(session)
    assert repository.cache_is_current("7001", record.sha256, PARSER_VERSION)
    assert not repository.cache_is_current("7001", record.sha256, "future-parser")
    view = repository.document_views(repository.list_documents())[0]
    assert len(view.references) == 2


@pytest.mark.asyncio
async def test_changed_sha_reparses_and_replaces_units(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_local_text(session, tmp_path, body=b"old control notes")
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    await service.ingest_file("7001")
    store_local(session, tmp_path, "7001", "lecture.txt", b"new gradient descent notes")
    result = await service.ingest_file("7001")
    document = DocumentRepository(session).get("7001")
    units = DocumentRepository(session).units_for("7001")
    assert result.parsed is True
    assert document is not None
    assert document.source_sha256 == hashlib.sha256(b"new gradient descent notes").hexdigest()
    assert [unit.text for unit in units] == ["new gradient descent notes"]


@pytest.mark.asyncio
async def test_changed_canvas_metadata_requires_incremental_redownload(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    old_body = b"old professor notes"
    new_body = b"revised professor notes"
    seed_local_text(session, tmp_path, body=old_body)
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    assert (await service.ingest_file("7001")).parsed is True

    # Canvas metadata changes while the last known-good local copy remains intact.
    seed_metadata(
        session,
        file_id="7001",
        filename="lecture.txt",
        body_size=len(new_body),
    )
    downloader = FakeDownloader(session, tmp_path, new_body)
    service = DocumentIngestionService(
        session=session,
        storage_root=tmp_path,
        limits=limits,
        downloader=downloader,
    )

    without_permission = await service.ingest_file("7001", canvas_course_id="101")
    document_before = DocumentRepository(session).get("7001")
    assert document_before is not None
    preserved_hash = document_before.source_sha256
    with_permission = await service.ingest_file(
        "7001", canvas_course_id="101", allow_download=True
    )

    assert without_permission.status == "download_required"
    assert preserved_hash == hashlib.sha256(old_body).hexdigest()
    assert downloader.calls == 1
    assert with_permission.parsed is True
    assert [unit.text for unit in DocumentRepository(session).units_for("7001")] == [
        "revised professor notes"
    ]


@pytest.mark.asyncio
async def test_parser_version_change_reprocesses_same_sha(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_local_text(session, tmp_path)
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    await service.ingest_file("7001")
    from app.services import document_ingestion

    original = document_ingestion.parse_document

    def version_two(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        return result.model_copy(update={"parser_version": "2"})

    monkeypatch.setattr(document_ingestion, "PARSER_VERSION", "2")
    monkeypatch.setattr(document_ingestion, "parse_document", version_two)
    outcome = await service.ingest_file("7001")
    document = DocumentRepository(session).get("7001")
    assert outcome.parsed is True
    assert document is not None and document.parser_version == "2"


def test_parser_version_participates_in_cache_identity(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_local_text(session, tmp_path)
    repository = DocumentRepository(session)
    record = FileRepository(session).get("7001")
    assert record is not None and record.sha256
    assert repository.cache_is_current("7001", record.sha256, PARSER_VERSION) is False


@pytest.mark.asyncio
async def test_failed_reparse_preserves_last_good_units(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_local_text(session, tmp_path, body=b"known good")
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    await service.ingest_file("7001")
    old_document = DocumentRepository(session).get("7001")
    assert old_document is not None and old_document.source_sha256
    old_hash = old_document.source_sha256
    store_local(session, tmp_path, "7001", "lecture.txt", b"changed source")

    def fail(*_: object, **__: object) -> object:
        raise DocumentParseError("malformed_document")

    monkeypatch.setattr("app.services.document_ingestion.parse_document", fail)
    outcome = await service.ingest_file("7001")
    document = DocumentRepository(session).get("7001")
    units = DocumentRepository(session).units_for("7001")
    assert outcome.status == "failed"
    assert document is not None
    assert document.status == "parsed"
    assert document.source_sha256 == old_hash
    assert document.last_attempt_status == "failed"
    assert document.last_error_category == "malformed_document"
    assert [unit.text for unit in units] == ["known good"]


@pytest.mark.asyncio
async def test_missing_corrupt_unsupported_and_no_provenance_are_safe(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(
        session,
        references=[("1001", "7001", "missing.txt"), ("1002", "7002", "program.exe")],
    )
    seed_metadata(session, file_id="7001", filename="missing.txt", body_size=3)
    seed_metadata(
        session,
        file_id="7002",
        filename="program.exe",
        body_size=4,
        content_type="application/octet-stream",
    )
    store_local(session, tmp_path, "7002", "program.exe", b"MZxx")
    seed_metadata(session, file_id="7999", filename="orphan.txt", body_size=1)
    store_local(session, tmp_path, "7999", "orphan.txt", b"x")
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    missing = await service.ingest_file("7001")
    unsupported = await service.ingest_file("7002")
    orphan = await service.ingest_file("7999")
    assert missing.status == "download_required"
    assert unsupported.error_category == "unsupported_executable"
    assert orphan.error_category == "no_academic_provenance"


class FakeDownloader:
    def __init__(self, session: Session, root: Path, body: bytes) -> None:
        self.session = session
        self.root = root
        self.body = body
        self.calls = 0

    async def download(
        self,
        *,
        canvas_file_id: str,
        canvas_course_id: str | None = None,
        force: bool = False,
    ) -> FileDownloadSummary:
        self.calls += 1
        record = FileRepository(self.session).get(canvas_file_id)
        assert record is not None and record.filename
        store_local(self.session, self.root, canvas_file_id, record.filename, self.body)
        return FileDownloadSummary(
            files_selected=1,
            files_downloaded=1,
            files_skipped=0,
            files_failed=0,
            files_too_large=0,
            files_inaccessible=0,
        )


@pytest.mark.asyncio
async def test_batch_isolates_sanitized_canvas_download_failure(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(
        session,
        references=[("1001", "7001", "missing.txt"), ("1002", "7002", "later.txt")],
    )
    seed_metadata(session, file_id="7001", filename="missing.txt", body_size=4)
    seed_metadata(session, file_id="7002", filename="later.txt", body_size=5)

    class IsolatingDownloader:
        async def download(
            self, *, canvas_file_id: str, **_: object
        ) -> FileDownloadSummary:
            if canvas_file_id == "7001":
                raise CanvasAPIError("unsafe signed URL detail", status_code=404)
            record = FileRepository(session).get(canvas_file_id)
            assert record is not None and record.filename
            store_local(session, tmp_path, canvas_file_id, record.filename, b"later")
            return FileDownloadSummary(
                files_selected=1,
                files_downloaded=1,
                files_skipped=0,
                files_failed=0,
                files_too_large=0,
                files_inaccessible=0,
            )

    summary = await DocumentIngestionService(
        session=session,
        storage_root=tmp_path,
        limits=limits,
        downloader=IsolatingDownloader(),
    ).ingest_files(["7001", "7002"], allow_download_ids=["7001", "7002"])

    assert summary.outcomes[0].status == "download_required"
    assert summary.outcomes[0].error_category == "inaccessible"
    assert summary.outcomes[1].parsed is True
    document = DocumentRepository(session).get("7001")
    assert document is not None
    assert document.last_error_category == "inaccessible"
    assert "unsafe" not in document.last_error_category


@pytest.mark.asyncio
async def test_missing_file_download_is_explicit_and_uses_injected_existing_downloader(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(session, references=[("1001", "7001", "lecture.txt")])
    body = b"downloaded academic notes"
    seed_metadata(session, file_id="7001", filename="lecture.txt", body_size=len(body))
    downloader = FakeDownloader(session, tmp_path, body)
    service = DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits, downloader=downloader
    )
    without_permission = await service.ingest_file("7001")
    with_permission = await service.ingest_file("7001", allow_download=True)
    assert without_permission.status == "download_required"
    assert downloader.calls == 1
    assert with_permission.parsed is True
    assert with_permission.downloaded is True
    assert with_permission.downloaded_bytes == len(body)


@pytest.mark.asyncio
async def test_batch_continues_after_parse_failure_and_course_plan_enforces_caps(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(
        session,
        references=[
            ("1001", "7001", "good.txt"),
            ("1002", "7002", "bad.pdf"),
            ("1003", "7003", "later.txt"),
        ],
    )
    for file_id, name, size, content_type in (
        ("7001", "good.txt", 4, "text/plain"),
        ("7002", "bad.pdf", 20, "application/pdf"),
        ("7003", "later.txt", 30, "text/plain"),
    ):
        seed_metadata(
            session,
            file_id=file_id,
            filename=name,
            body_size=size,
            content_type=content_type,
        )
    store_local(session, tmp_path, "7001", "good.txt", b"good")
    store_local(session, tmp_path, "7002", "bad.pdf", b"%PDF-not-valid-data")
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    summary = await service.ingest_files(["7001", "7002", "7003"])
    plan = service.plan_course("101", max_new_download_files=1, max_new_download_bytes=25)
    assert summary.files_parsed == 1
    assert summary.files_failed == 1
    assert summary.files_download_required == 1
    assert plan.eligible_files == 3
    assert plan.already_local_files == 2
    assert plan.new_download_files == 0
    assert plan.deferred_files == 1


@pytest.mark.asyncio
async def test_course_ingestion_enforces_file_and_byte_download_caps(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(
        session,
        references=[
            ("1001", "7001", "a.txt"),
            ("1002", "7002", "b.txt"),
            ("1003", "7003", "c.txt"),
        ],
    )
    bodies = {"7001": b"a" * 10, "7002": b"b" * 12, "7003": b"c" * 5}
    for file_id, name in (("7001", "a.txt"), ("7002", "b.txt"), ("7003", "c.txt")):
        seed_metadata(
            session, file_id=file_id, filename=name, body_size=len(bodies[file_id])
        )

    class BatchDownloader:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def download(self, *, canvas_file_id: str, **_: object) -> FileDownloadSummary:
            self.calls.append(canvas_file_id)
            record = FileRepository(session).get(canvas_file_id)
            assert record is not None and record.filename
            store_local(session, tmp_path, canvas_file_id, record.filename, bodies[canvas_file_id])
            return FileDownloadSummary(
                files_selected=1,
                files_downloaded=1,
                files_skipped=0,
                files_failed=0,
                files_too_large=0,
                files_inaccessible=0,
            )

    downloader = BatchDownloader()
    summary = await DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits, downloader=downloader
    ).ingest_course(
        "101", allow_download=True, max_new_download_files=2, max_new_download_bytes=25
    )
    assert downloader.calls == ["7001", "7002"]
    assert summary.files_downloaded == 2
    assert summary.downloaded_bytes == 22
    assert summary.files_download_required == 1


@pytest.mark.asyncio
async def test_incremental_course_knowledge_is_fair_bounded_and_idempotent(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(
        session,
        course_id="101",
        module_id="201",
        references=[("101-a", "file-a", "A"), ("101-b", "file-b", "B")],
    )
    seed_references(
        session,
        course_id="102",
        module_id="202",
        references=[("102-c", "file-c", "C")],
    )
    bodies = {"file-a": b"alpha", "file-b": b"bravo", "file-c": b"charlie"}
    for file_id, body in bodies.items():
        seed_metadata(session, file_id=file_id, filename=f"{file_id}.txt", body_size=len(body))

    class Downloader:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []

        async def download(
            self, *, canvas_file_id: str, canvas_course_id: str | None = None, **_: object
        ) -> FileDownloadSummary:
            self.calls.append((canvas_file_id, canvas_course_id))
            record = FileRepository(session).get(canvas_file_id)
            assert record is not None and record.filename
            store_local(
                session,
                tmp_path,
                canvas_file_id,
                record.filename,
                bodies[canvas_file_id],
            )
            return FileDownloadSummary(
                files_selected=1,
                files_downloaded=1,
                files_skipped=0,
                files_failed=0,
                files_too_large=0,
                files_inaccessible=0,
            )

    downloader = Downloader()
    service = DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits, downloader=downloader
    )
    first = await service.prepare_courses(
        ["101", "102"], max_new_download_files=2, max_new_download_bytes=20
    )
    second = await service.prepare_courses(
        ["101", "102"], max_new_download_files=2, max_new_download_bytes=20
    )

    assert downloader.calls[:2] == [("file-a", "101"), ("file-c", "102")]
    assert first.files_downloaded == 2
    assert first.files_deferred == 1
    assert second.files_unchanged == 2
    assert second.files_downloaded == 1
    assert len(downloader.calls) == 3


@pytest.mark.asyncio
async def test_hostile_canvas_filename_cannot_control_parser_path(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    hostile = "..\\..\\CON.txt"
    seed_references(session, references=[("1001", "7001", hostile)])
    seed_metadata(session, file_id="7001", filename=hostile, body_size=4)
    store_local(session, tmp_path, "7001", hostile, b"safe")
    outcome = await DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits
    ).ingest_file("7001")
    assert outcome.parsed is True
    record = FileRepository(session).get("7001")
    assert record is not None and record.local_relative_path
    assert ".." not in Path(record.local_relative_path).parts


@pytest.mark.asyncio
async def test_database_error_rolls_back_partial_replacement(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_local_text(session, tmp_path, body=b"stable text")
    service = DocumentIngestionService(session=session, storage_root=tmp_path, limits=limits)
    await service.ingest_file("7001")

    def fail_after_delete(self: DocumentRepository, **_: object) -> object:
        document = self.get("7001")
        assert document is not None
        self._session.query(DocumentUnit).filter(DocumentUnit.document_id == document.id).delete()
        from sqlalchemy.exc import IntegrityError

        raise IntegrityError("safe", {}, Exception("safe"))

    monkeypatch.setattr(DocumentRepository, "replace_success", fail_after_delete)
    store_local(session, tmp_path, "7001", "lecture.txt", b"new text")
    outcome = await service.ingest_file("7001")
    assert outcome.error_category == "database_error"
    assert [unit.text for unit in DocumentRepository(session).units_for("7001")] == ["stable text"]
