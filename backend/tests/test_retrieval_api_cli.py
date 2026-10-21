import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.database.session import get_session
from app.documents.models import DocumentLimits
from app.files.downloader import ControlledFileDownloader
from app.main import app
from app.services.document_ingestion import DocumentIngestionService
from app.sync import retrieval_cli
from sqlalchemy.orm import Session, sessionmaker

from tests.test_document_ingestion import seed_local_text


@pytest.fixture
def limits() -> DocumentLimits:
    return DocumentLimits(
        max_source_bytes=5_000_000,
        max_characters=20_000,
        max_units=100,
        max_unit_characters=80,
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
async def test_retrieval_apis_are_local_only_bounded_and_safe(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge_id = "999999999999999999999999999999"
    with session_factory() as session:
        seed_local_text(
            session,
            tmp_path,
            file_id=huge_id,
            filename="robotics.txt",
            body=(b"forward kinematics and robot coordinate frames. " * 8),
        )
        await DocumentIngestionService(
            session=session, storage_root=tmp_path, limits=limits
        ).ingest_file(huge_id)

    async def fail_network(*_: object, **__: object) -> object:
        raise AssertionError("retrieval APIs must remain local-only")

    monkeypatch.setattr(CanvasClient, "get_json", fail_network)
    monkeypatch.setattr(CanvasClient, "get_paginated", fail_network)
    monkeypatch.setattr(ControlledFileDownloader, "download", fail_network)
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            search = await client.get(
                "/api/retrieval/search",
                params={"q": "forward kinematics", "course_id": "101", "limit": 2},
            )
            hybrid = await client.get(
                "/api/retrieval/search",
                params={"q": "forward kinematics", "mode": "hybrid"},
            )
            context = await client.get(
                "/api/retrieval/context",
                params={"q": "forward kinematics", "max_characters": 30},
            )
            neighbors = await client.get(
                f"/api/retrieval/documents/{huge_id}/units/1/context",
                params={"before": 1, "after": 1, "max_characters": 100},
            )
            source = await client.get(f"/api/retrieval/documents/{huge_id}/source")
    finally:
        app.dependency_overrides.clear()

    assert search.status_code == hybrid.status_code == context.status_code == 200
    assert neighbors.status_code == source.status_code == 200
    payload = search.json()
    assert payload["results"][0]["evidence"]["canvas_file_id"] == huge_id
    assert payload["results"][0]["evidence"]["authority"] == "professor_material"
    assert hybrid.json()["semantic_status"] == "unavailable"
    assert context.json()["characters_used"] <= 30
    encoded = json.dumps(
        [search.json(), hybrid.json(), context.json(), neighbors.json(), source.json()]
    ).casefold()
    for forbidden in (
        "local_relative_path",
        "authorization",
        "canvas_token",
        "x-amz-signature",
        "sf_verifier",
        "file://",
    ):
        assert forbidden not in encoded


@pytest.mark.asyncio
async def test_retrieval_api_validation_and_not_found(
    session_factory: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            empty = await client.get("/api/retrieval/search", params={"q": ""})
            bad_id = await client.get(
                "/api/retrieval/search", params={"q": "term", "file_id": "bad id"}
            )
            bad_mode = await client.get(
                "/api/retrieval/search", params={"q": "term", "mode": "cloud"}
            )
            bad_limit = await client.get(
                "/api/retrieval/search", params={"q": "term", "limit": 101}
            )
            missing = await client.get(
                "/api/retrieval/documents/999999999999999999/source"
            )
    finally:
        app.dependency_overrides.clear()
    assert empty.status_code == bad_id.status_code == bad_mode.status_code == 422
    assert bad_limit.status_code == 422
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_retrieval_cli_outputs_bounded_local_json_without_secrets(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with session_factory() as session:
        seed_local_text(
            session,
            tmp_path,
            body=b"project requirements remain deterministic",
        )
        await DocumentIngestionService(
            session=session, storage_root=tmp_path, limits=limits
        ).ingest_file("7001")
    monkeypatch.setattr(retrieval_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(retrieval_cli, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "academic-retrieve",
            "project requirements",
            "--course-id",
            "101",
            "--context-package",
            "--max-context-characters",
            "40",
        ],
    )
    assert retrieval_cli.run() == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["authority"] == "professor_material"
    assert payload["characters_used"] <= 40
    assert "Authorization" not in output
    assert "CANVAS_TOKEN" not in output
    assert "local_relative_path" not in output
    assert "http" not in output
