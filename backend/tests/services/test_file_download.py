import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.canvas.files import normalize_file
from app.database.file_repository import FileRepository
from app.database.models import CanvasFile
from app.files.downloader import ControlledFileDownloader
from app.files.models import CanvasFileMetadata
from app.services.file_download import FileDownloadService
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from tests.factories import canvas_file_payload
from tests.files.test_downloader import BrokenStream, allow_test_destination


class Source:
    def __init__(self, metadata: CanvasFileMetadata) -> None:
        self.metadata = metadata
        self.calls = 0

    async def fetch_file(self, _: str) -> CanvasFileMetadata:
        self.calls += 1
        return self.metadata


def seed_file(session: Session, metadata: CanvasFileMetadata) -> CanvasFile:
    FileRepository(session).synchronize(
        [metadata.snapshot], synced_at=datetime(2026, 9, 28, tzinfo=UTC)
    )
    session.commit()
    record = FileRepository(session).get(metadata.snapshot.canvas_file_id)
    assert record is not None
    return record


def downloader(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_bytes: int = 1000,
) -> ControlledFileDownloader:
    return ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=max_bytes,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    )


@pytest.mark.asyncio
async def test_success_persists_hash_size_relative_path_and_opaque_bytes_only_on_disk(
    session: Session, tmp_path: Path
) -> None:
    body = b"opaque academic file bytes"
    metadata = normalize_file(canvas_file_payload(size=len(body)))
    seed_file(session, metadata)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/pdf"},
            request=request,
        )

    source = Source(metadata)
    async with downloader(handler) as client:
        summary = await FileDownloadService(
            source=source, downloader=client, session=session, storage_root=tmp_path
        ).download(canvas_file_id="7001")

    record = FileRepository(session).get("7001")
    assert summary.files_downloaded == 1
    assert record is not None
    assert record.sha256 == hashlib.sha256(body).hexdigest()
    assert record.local_size == len(body)
    assert record.local_relative_path is not None
    assert not Path(record.local_relative_path).is_absolute()
    assert (tmp_path / record.local_relative_path).read_bytes() == body
    assert session.bind is not None
    columns = inspect(session.bind).get_columns("canvas_files")
    assert all(column["type"].python_type is not bytes for column in columns)


@pytest.mark.asyncio
async def test_unchanged_valid_copy_skips_and_force_redownloads(
    session: Session, tmp_path: Path
) -> None:
    calls = 0
    metadata = normalize_file(canvas_file_payload(size=3))
    seed_file(session, metadata)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"one", request=request)

    source = Source(metadata)
    async with downloader(handler) as client:
        service = FileDownloadService(
            source=source, downloader=client, session=session, storage_root=tmp_path
        )
        first = await service.download(canvas_file_id="7001")
        second = await service.download(canvas_file_id="7001")
        forced = await service.download(canvas_file_id="7001", force=True)

    assert first.files_downloaded == 1
    assert second.files_skipped == 1
    assert forced.files_downloaded == 1
    assert calls == 2
    assert source.calls == 2


@pytest.mark.asyncio
async def test_missing_local_copy_triggers_redownload(session: Session, tmp_path: Path) -> None:
    metadata = normalize_file(canvas_file_payload(size=3))
    seed_file(session, metadata)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"one", request=request)

    source = Source(metadata)
    async with downloader(handler) as client:
        service = FileDownloadService(
            source=source, downloader=client, session=session, storage_root=tmp_path
        )
        await service.download(canvas_file_id="7001")
        record = FileRepository(session).get("7001")
        assert record is not None and record.local_relative_path
        (tmp_path / record.local_relative_path).unlink()
        result = await service.download(canvas_file_id="7001")
    assert result.files_downloaded == 1


@pytest.mark.asyncio
async def test_failed_replacement_preserves_previous_good_copy_and_state(
    session: Session, tmp_path: Path
) -> None:
    first_metadata = normalize_file(canvas_file_payload(filename="old.pdf", size=3))
    seed_file(session, first_metadata)

    def success(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"old", request=request)

    first_source = Source(first_metadata)
    async with downloader(success) as client:
        await FileDownloadService(
            source=first_source, downloader=client, session=session, storage_root=tmp_path
        ).download(canvas_file_id="7001")
    record = FileRepository(session).get("7001")
    assert record is not None and record.local_relative_path
    old_path = tmp_path / record.local_relative_path

    changed = normalize_file(
        canvas_file_payload(filename="new.pdf", size=10, updated_at="2026-09-29T12:00:00Z")
    )
    FileRepository(session).synchronize(
        [changed.snapshot], synced_at=datetime(2026, 9, 29, tzinfo=UTC)
    )
    session.commit()

    def interrupted(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=BrokenStream(), request=request)

    async with downloader(interrupted) as client:
        summary = await FileDownloadService(
            source=Source(changed), downloader=client, session=session, storage_root=tmp_path
        ).download(canvas_file_id="7001")

    record = FileRepository(session).get("7001")
    assert summary.files_failed == 1
    assert old_path.read_bytes() == b"old"
    assert record is not None
    assert record.download_state == "downloaded"
    assert record.local_relative_path == old_path.relative_to(tmp_path).as_posix()
    assert record.last_download_error == "failed"
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_oversize_download_records_state_without_final_file(
    session: Session, tmp_path: Path
) -> None:
    metadata = normalize_file(canvas_file_payload(size=100))
    seed_file(session, metadata)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"01234567890", request=request)

    async with downloader(handler, max_bytes=10) as client:
        summary = await FileDownloadService(
            source=Source(metadata), downloader=client, session=session, storage_root=tmp_path
        ).download(canvas_file_id="7001")
    record = session.scalar(select(CanvasFile).where(CanvasFile.canvas_file_id == "7001"))
    assert summary.files_too_large == 1
    assert record is not None and record.download_state == "too_large"
    assert not list(tmp_path.rglob("*.pdf"))
