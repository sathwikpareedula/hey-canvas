"""Read-only Canvas file metadata retrieval and defensive normalization."""

from datetime import datetime
from typing import Any
from urllib.parse import quote

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.canvas.client import CanvasClient
from app.canvas.courses import _clean_optional_text, _normalize_canvas_id, _normalize_datetime
from app.canvas.exceptions import CanvasResponseError
from app.files.models import CanvasFileMetadata, FileSnapshot


class _CanvasFilePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    folder_id: str | int | None = None
    display_name: str | None = None
    filename: str | None = None
    content_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("content-type", "content_type"),
    )
    url: str | None = None
    size: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    modified_at: datetime | None = None
    unlock_at: datetime | None = None
    lock_at: datetime | None = None
    locked: bool | None = None
    hidden: bool | None = None
    hidden_for_user: bool | None = None
    visibility_level: str | None = None

    @field_validator("id", "folder_id", mode="before")
    @classmethod
    def reject_boolean_ids(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas file identifiers cannot be boolean")
        return value

    @field_validator("size", mode="before")
    @classmethod
    def reject_boolean_size(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas file size cannot be boolean")
        return value

    @field_validator("created_at", "updated_at", "modified_at", "unlock_at", "lock_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class CanvasFileSource:
    """Fetch global Canvas file metadata by documented file ID endpoint."""

    def __init__(self, client: CanvasClient) -> None:
        self._client = client

    async def fetch_file(self, canvas_file_id: str) -> CanvasFileMetadata:
        normalized = _normalize_canvas_id(canvas_file_id, field_name="file id")
        payload = await self._client.get_json(f"/api/v1/files/{quote(normalized, safe='~')}")
        if not isinstance(payload, dict):
            raise CanvasResponseError("Canvas file endpoint returned an unexpected JSON shape")
        metadata = normalize_file(payload)
        if metadata.snapshot.canvas_file_id != normalized:
            raise CanvasResponseError("Canvas file response ID did not match the requested file")
        return metadata


def normalize_file(payload: dict[str, Any]) -> CanvasFileMetadata:
    """Normalize a File object without retaining or echoing its signed URL."""

    try:
        item = _CanvasFilePayload.model_validate(payload)
        file_id = _normalize_canvas_id(item.id, field_name="file id")
        folder_id = (
            _normalize_canvas_id(item.folder_id, field_name="folder id")
            if item.folder_id is not None
            else None
        )
        if item.size is not None and item.size < 0:
            raise ValueError("Canvas file size cannot be negative")
    except (ValidationError, ValueError, TypeError) as exc:
        raise CanvasResponseError("Canvas file object is malformed") from exc

    return CanvasFileMetadata(
        snapshot=FileSnapshot(
            canvas_file_id=file_id,
            display_name=_clean_optional_text(item.display_name),
            filename=_clean_optional_text(item.filename),
            content_type=_clean_optional_text(item.content_type),
            size=item.size,
            folder_id=folder_id,
            canvas_created_at=item.created_at,
            canvas_updated_at=item.updated_at,
            canvas_modified_at=item.modified_at,
            unlock_at=item.unlock_at,
            lock_at=item.lock_at,
            locked=item.locked,
            hidden=item.hidden,
            hidden_for_user=item.hidden_for_user,
            visibility_level=_clean_optional_text(item.visibility_level),
        ),
        download_url=_clean_optional_text(item.url),
    )
