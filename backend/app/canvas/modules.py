"""Canvas module and module-item retrieval with defensive normalization."""

from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.canvas.client import CanvasClient
from app.canvas.courses import _clean_optional_text, _normalize_canvas_id, _normalize_datetime
from app.canvas.exceptions import CanvasResponseError
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot


class _CanvasModulePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    name: str | None = None
    position: int | None = None
    unlock_at: datetime | None = None
    require_sequential_progress: bool | None = None
    requirement_type: str | None = None
    publish_final_grade: bool | None = None
    prerequisite_module_ids: list[str | int] | None = None
    workflow_state: str | None = None
    state: str | None = None
    completed_at: datetime | None = None
    items_count: int | None = None
    published: bool | None = None
    items: list[dict[str, Any]] | None = None

    @field_validator("id", mode="before")
    @classmethod
    def reject_boolean_id(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas module id cannot be boolean")
        return value

    @field_validator("position", "items_count", mode="before")
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas integer fields cannot be boolean")
        return value

    @field_validator("unlock_at", "completed_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class _CanvasModuleItemPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    module_id: str | int | None = None
    title: str | None = None
    position: int | None = None
    type: str
    content_id: str | int | None = None
    html_url: str | None = None
    url: str | None = None
    page_url: str | None = None
    external_url: str | None = None
    new_tab: bool | None = None
    completion_requirement: dict[str, Any] | None = None
    content_details: dict[str, Any] | None = None
    indent: int | None = None
    published: bool | None = None

    @field_validator("id", "module_id", "content_id", mode="before")
    @classmethod
    def reject_boolean_ids(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas identifiers cannot be boolean")
        return value

    @field_validator("position", "indent", mode="before")
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas integer fields cannot be boolean")
        return value


class CanvasModuleSource:
    """Fetch one course's complete module structure before returning it."""

    def __init__(self, client: CanvasClient) -> None:
        self._client = client

    async def fetch_course_modules(self, canvas_course_id: str) -> list[ModuleSnapshot]:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        encoded_course_id = quote(course_id, safe="~")
        payloads = await self._client.get_paginated(
            f"/api/v1/courses/{encoded_course_id}/modules",
            params=httpx.QueryParams(
                [
                    ("include[]", "items"),
                    ("include[]", "content_details"),
                    ("per_page", "100"),
                ]
            ),
        )

        snapshots: list[ModuleSnapshot] = []
        for index, payload in enumerate(payloads):
            module = _parse_module(payload, index=index)
            module_id = _module_id(module, index=index)
            item_payloads = module.items
            if item_payloads is None:
                encoded_module_id = quote(module_id, safe="~")
                item_payloads = await self._client.get_paginated(
                    f"/api/v1/courses/{encoded_course_id}/modules/{encoded_module_id}/items",
                    params=httpx.QueryParams(
                        [("include[]", "content_details"), ("per_page", "100")]
                    ),
                )
            snapshots.append(
                _module_snapshot(
                    module,
                    item_payloads=item_payloads,
                    canvas_course_id=course_id,
                    index=index,
                )
            )
        return snapshots


def normalize_module(
    payload: dict[str, Any],
    *,
    canvas_course_id: str,
    index: int = 0,
) -> ModuleSnapshot:
    """Normalize one module and any inline items without echoing its content."""

    module = _parse_module(payload, index=index)
    return _module_snapshot(
        module,
        item_payloads=module.items or [],
        canvas_course_id=canvas_course_id,
        index=index,
    )


def normalize_module_item(
    payload: dict[str, Any],
    *,
    canvas_course_id: str,
    canvas_module_id: str,
    index: int = 0,
) -> ModuleItemSnapshot:
    """Normalize an item while accepting unknown future item type strings."""

    try:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        module_id = _normalize_canvas_id(canvas_module_id, field_name="module id")
        item = _CanvasModuleItemPayload.model_validate(payload)
        item_id = _normalize_canvas_id(item.id, field_name="module item id")
        if item.module_id is not None:
            response_module_id = _normalize_canvas_id(item.module_id, field_name="item module id")
            if response_module_id != module_id:
                raise ValueError("module item does not belong to the requested module")
        content_id = (
            _normalize_canvas_id(item.content_id, field_name="content id")
            if item.content_id is not None
            else None
        )
        item_type = _clean_optional_text(item.type)
        if item_type is None:
            raise ValueError("module item type is empty")
    except (ValidationError, ValueError, TypeError) as exc:
        raise CanvasResponseError(
            f"Canvas module item object at index {index} is malformed"
        ) from exc

    return ModuleItemSnapshot(
        canvas_module_item_id=item_id,
        canvas_module_id=module_id,
        canvas_course_id=course_id,
        title=_clean_optional_text(item.title),
        position=item.position,
        item_type=item_type,
        content_id=content_id,
        html_url=_clean_optional_text(item.html_url),
        api_url=_clean_optional_text(item.url),
        page_url=_clean_optional_text(item.page_url),
        external_url=_clean_optional_text(item.external_url),
        new_tab=item.new_tab,
        completion_requirement=item.completion_requirement,
        content_details=item.content_details,
        indent=item.indent,
        published=item.published,
    )


def _parse_module(payload: dict[str, Any], *, index: int) -> _CanvasModulePayload:
    try:
        return _CanvasModulePayload.model_validate(payload)
    except ValidationError as exc:
        raise CanvasResponseError(f"Canvas module object at index {index} is malformed") from exc


def _module_id(module: _CanvasModulePayload, *, index: int) -> str:
    try:
        return _normalize_canvas_id(module.id, field_name="module id")
    except (ValueError, TypeError) as exc:
        raise CanvasResponseError(f"Canvas module object at index {index} is malformed") from exc


def _module_snapshot(
    module: _CanvasModulePayload,
    *,
    item_payloads: list[dict[str, Any]],
    canvas_course_id: str,
    index: int,
) -> ModuleSnapshot:
    try:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        module_id = _normalize_canvas_id(module.id, field_name="module id")
        prerequisite_ids = tuple(
            _normalize_canvas_id(value, field_name="prerequisite module id")
            for value in module.prerequisite_module_ids or []
        )
        items = tuple(
            normalize_module_item(
                item,
                canvas_course_id=course_id,
                canvas_module_id=module_id,
                index=item_index,
            )
            for item_index, item in enumerate(item_payloads)
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise CanvasResponseError(f"Canvas module object at index {index} is malformed") from exc

    return ModuleSnapshot(
        canvas_module_id=module_id,
        canvas_course_id=course_id,
        name=_clean_optional_text(module.name),
        position=module.position,
        unlock_at=module.unlock_at,
        require_sequential_progress=module.require_sequential_progress,
        requirement_type=_clean_optional_text(module.requirement_type),
        publish_final_grade=module.publish_final_grade,
        prerequisite_module_ids=prerequisite_ids,
        workflow_state=_clean_optional_text(module.workflow_state),
        state=_clean_optional_text(module.state),
        completed_at=module.completed_at,
        items_count=module.items_count,
        published=module.published,
        items=items,
    )
