import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.config import Settings
from app.database.session import get_session
from app.documents.models import DocumentLimits
from app.main import app
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_search import DocumentSearchService
from app.services.file_download import FileDownloadService
from app.sync import documents_cli
from sqlalchemy.orm import Session, sessionmaker

from tests.test_document_ingestion import seed_local_text


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


def override_factory(factory: sessionmaker[Session]) -> Callable[[], Iterator[Session]]:
    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    return override


@pytest.mark.asyncio
async def test_lexical_search_is_stable_bounded_filtered_and_has_provenance(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_local_text(
        session,
        tmp_path,
        file_id="7001",
        filename="robotics.txt",
        body=b"Inverse kinematics uses iterative inverse kinematics methods.",
    )
    service = DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits
    )
    await service.ingest_file("7001")
    results = DocumentSearchService(session).search(
        "inverse kinematics", canvas_course_id="101", limit=1
    )
    assert len(results) == 1
    assert results[0].canvas_file_id == "7001"
    assert results[0].score > 0
    assert "Inverse kinematics" in results[0].snippet
    assert results[0].source_sha256
    assert results[0].is_stale is False
    assert results[0].references[0].canvas_course_id == "101"
    assert DocumentSearchService(session).search(
        "inverse kinematics", canvas_course_id="999"
    ) == []
    assert DocumentSearchService(session).search(
        "inverse kinematics", canvas_file_id="999"
    ) == []
    partial = DocumentSearchService(session).search(
        "inverse kinematics extra tokens that are not in the file",
        canvas_course_id="101",
        limit=1,
    )
    assert len(partial) == 1


@pytest.mark.asyncio
async def test_document_apis_are_local_only_and_serialize_safe_provenance(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        seed_local_text(session, tmp_path)
        await DocumentIngestionService(
            session=session, storage_root=tmp_path, limits=limits
        ).ingest_file("7001")

    async def fail_network(*_: object, **__: object) -> object:
        raise AssertionError("document GET endpoints must not contact Canvas or download")

    monkeypatch.setattr(CanvasClient, "get_json", fail_network)
    monkeypatch.setattr(FileDownloadService, "download", fail_network)
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            listed = await client.get("/api/documents", params={"course_id": "101"})
            one = await client.get("/api/documents/7001")
            units = await client.get("/api/documents/7001/units")
            search = await client.get(
                "/api/document-search",
                params={"q": "inverse kinematics", "course_id": "101"},
            )
            coverage = await client.get("/api/courses/101/document-coverage")
            missing = await client.get("/api/documents/9999")
            invalid = await client.get("/api/documents", params={"limit": 0})
    finally:
        app.dependency_overrides.clear()

    assert (
        listed.status_code
        == one.status_code
        == units.status_code
        == search.status_code
        == coverage.status_code
        == 200
    )
    assert missing.status_code == 404
    assert invalid.status_code == 422
    document = one.json()
    assert document["canvas_file_id"] == "7001"
    assert document["references"][0]["canvas_module_item_id"] == "1001"
    assert "local_relative_path" not in document
    assert "url" not in document
    unit = units.json()[0]
    assert unit["source_sha256"]
    assert unit["references"][0]["canvas_module_id"] == "201"
    assert search.json()[0]["page_number"] is None
    assert all("url" not in key.lower() for key in search.json()[0])
    assert coverage.json() == {
        "canvas_course_id": "101",
        "known_files": 1,
        "eligible_files": 1,
        "indexed_current": 1,
        "indexed_stale": 0,
        "awaiting_download": 0,
        "needs_ocr": 0,
        "unsupported": 0,
        "failed": 0,
    }


@pytest.mark.asyncio
async def test_search_api_validates_query_file_and_limits(
    session_factory: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            empty = await client.get("/api/document-search", params={"q": ""})
            bad_file = await client.get(
                "/api/document-search", params={"q": "term", "file_id": "bad id"}
            )
            too_many = await client.get(
                "/api/document-search", params={"q": "term", "limit": 101}
            )
    finally:
        app.dependency_overrides.clear()
    assert empty.status_code == bad_file.status_code == too_many.status_code == 422


def test_search_cli_outputs_local_json_without_secret(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(documents_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(documents_cli, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(sys, "argv", ["academic-document-search", "nothing"])
    assert documents_cli.run_search() == 0
    output = capsys.readouterr().out
    assert output.strip() == "[]"
    assert "Authorization" not in output
    assert "CANVAS_TOKEN" not in output


def test_ingest_file_cli_summary_is_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(documents_cli, "_run_ingestion", lambda **_: 0)
    monkeypatch.setattr(sys, "argv", ["academic-ingest-file", "--file-id", "7001"])
    assert documents_cli.run_file() == 0
    output = capsys.readouterr().out
    assert "Authorization" not in output
    assert "http" not in output


def test_ingest_cli_missing_credentials_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        documents_cli,
        "get_settings",
        lambda: Settings(_env_file=None, canvas_base_url=None, canvas_token=None),
    )
    monkeypatch.setattr(documents_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["academic-ingest-file", "--file-id", "7001", "--download"],
    )
    assert documents_cli.run_file() == 1
    captured = capsys.readouterr()
    assert "CANVAS_TOKEN" in captured.err
    assert "Bearer" not in captured.err
    assert "Authorization" not in captured.err
