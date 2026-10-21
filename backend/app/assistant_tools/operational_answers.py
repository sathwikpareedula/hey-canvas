"""Deterministic answers about sync health, focus courses, missing evidence and ambiguity.

These never call a model: each states only what the local database can prove and says
plainly when something is unknown, stale, unreadable or ambiguous.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.assistant_tools.deterministic_answers import format_due
from app.assistant_tools.models import (
    AssignmentToolRecord,
    AssistantResponse,
    AssistantResponseBlock,
    ResponseBlockType,
)

STALE_AFTER = timedelta(hours=48)
_UNHEALTHY = {"failed", "interrupted", "partially_succeeded"}
_FOCUS_ASSIGNMENT_LIMIT = 25


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _age_phrase(delta: timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 90:
        return "moments ago"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hours ago"
    return f"{hours // 24} days ago"


def sync_caveat(sync: Mapping[str, object] | None, *, now: datetime) -> str | None:
    """Return a warning when answers rest on an unhealthy or stale sync, else None.

    A database that has never synced returns None: it is either a demo or a local
    fixture and there is no "failed" sync to be misleading about.
    """
    if not sync or sync.get("status") in {None, "not_run"}:
        return None
    status = sync.get("status")
    if status == "failed" or status == "interrupted":
        return (
            "Note: your last Canvas sync failed, so this answer may be out of date. "
            "Run a new sync to refresh it."
        )
    if status == "partially_succeeded":
        return (
            "Note: your last Canvas sync only partly succeeded, so some items may be "
            "missing or out of date. Run a new sync to refresh them."
        )
    finished = _parse(sync.get("finished_at")) or _parse(sync.get("started_at"))
    if status == "succeeded" and finished is not None and now - finished > STALE_AFTER:
        return (
            f"Note: your last successful Canvas sync was {_age_phrase(now - finished)}, "
            "so this answer may be out of date. Run a new sync to refresh it."
        )
    return None


def with_caveat(response: AssistantResponse, caveat: str | None) -> AssistantResponse:
    if not caveat or not response.blocks:
        return response
    first = response.blocks[0]
    if first.type is not ResponseBlockType.TEXT or not first.text:
        return response
    return AssistantResponse(
        status=response.status,
        blocks=(
            AssistantResponseBlock(type=ResponseBlockType.TEXT, text=f"{first.text}\n\n{caveat}"),
            *response.blocks[1:],
        ),
        course_id=response.course_id,
    )


def build_sync_status_answer(
    sync: Mapping[str, object], *, now: datetime, timezone: ZoneInfo
) -> AssistantResponse:
    status = sync.get("status")
    finished = _parse(sync.get("finished_at")) or _parse(sync.get("started_at"))
    when = ""
    if finished is not None:
        when = f" ({format_due(finished, timezone=timezone)})"
    errors = sync.get("error_count")
    if status == "not_run" or status is None:
        text = (
            "Canvas has not been synced on this computer yet, so I have no course data "
            "to rely on. Run a sync first."
        )
    elif status == "running":
        text = "A Canvas sync is running right now. Ask again when it finishes."
    elif status in {"failed", "interrupted"}:
        text = (
            f"Your last Canvas sync {'failed' if status == 'failed' else 'was interrupted'}"
            f"{when}. I can only use what was synced earlier, and it may be out of date. "
            "Run a new sync."
        )
    elif status == "partially_succeeded":
        count = f" with {errors} error(s)" if isinstance(errors, int) and errors else ""
        text = (
            f"Your last Canvas sync only partly succeeded{count}{when}. "
            "Some courses, files or assignments may be missing or out of date."
        )
    elif finished is not None and now - finished > STALE_AFTER:
        text = (
            f"Your last successful Canvas sync was {_age_phrase(now - finished)}{when}, "
            "so deadlines and materials may be out of date. Run a new sync."
        )
    else:
        age = _age_phrase(now - finished) if finished is not None else "recently"
        text = f"Your Canvas data is current: the last sync succeeded {age}{when}."
    return AssistantResponse(
        status="ok",
        blocks=(
            AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
            AssistantResponseBlock(type=ResponseBlockType.SYNC_STATUS, payload=dict(sync)),
        ),
    )


def build_focus_assignments_answer(
    focus: Sequence[tuple[str, str | None]],
    assignments: Mapping[str, Sequence[AssignmentToolRecord]],
    *,
    timezone: ZoneInfo,
) -> AssistantResponse:
    """``focus`` is ``(canvas_course_id, course_name)`` in the student's chosen order."""
    if not focus:
        text = (
            "You have not selected a focus course yet. Choose one in your course "
            "settings and I will list its assignments."
        )
        return AssistantResponse(
            status="ok",
            blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
        )
    lines: list[str] = []
    shown = 0
    omitted = 0
    for course_id, course_name in focus:
        items = sorted(
            assignments.get(course_id, ()),
            key=lambda a: (a.due_at is None, a.due_at or datetime.max.replace(tzinfo=UTC)),
        )
        lines.append(f"{course_name or 'Course'}:")
        if not items:
            lines.append("• No assignments are synced for this course.")
        for item in items:
            if shown >= _FOCUS_ASSIGNMENT_LIMIT:
                omitted += 1
                continue
            shown += 1
            due = (
                format_due(item.due_at, timezone=timezone)
                if item.due_at
                else "no due date listed in Canvas"
            )
            points = "" if item.points_possible is None else f", {item.points_possible:g} points"
            lines.append(f"• {item.name or 'Untitled assignment'} — {due}{points}")
    if omitted:
        lines.append(f"…and {omitted} more.")
    return AssistantResponse(
        status="ok",
        blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text="\n".join(lines)),),
    )


def build_no_evidence_answer(
    *, course_name: str | None, unreadable_titles: Sequence[str]
) -> AssistantResponse:
    where = f" in {course_name}" if course_name else ""
    text = (
        f"I couldn't find indexed material{where} that matches that, so I won't "
        "guess at what the professor said."
    )
    if course_name is None:
        text += " Tell me which course you mean so I can search its materials."
    if unreadable_titles:
        shown = ", ".join(unreadable_titles[:5])
        text += (
            " Some files in this course have no readable text (they may be scanned images "
            f"and OCR is not available yet): {shown}. Their contents are unknown to me."
        )
    return AssistantResponse(
        status="ok",
        blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
    )


def build_assignment_ambiguity_answer(
    candidates: Sequence[tuple[AssignmentToolRecord, str | None]],
    *,
    timezone: ZoneInfo,
) -> AssistantResponse:
    title = candidates[0][0].name or "That assignment"
    lines = [f'"{title}" exists in more than one course. Which one do you mean?']
    for record, course_name in candidates:
        due = (
            f"due {format_due(record.due_at, timezone=timezone)}"
            if record.due_at
            else "no due date listed in Canvas"
        )
        lines.append(f"• {title} ({course_name or 'Course'}) — {due}")
    return AssistantResponse(
        status="ok",
        blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text="\n".join(lines)),),
    )
