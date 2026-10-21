"""Deterministic, timezone-aware deadline window queries."""

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.database.assignment_repository import AssignmentRepository
from app.database.models import Assignment


class DeadlineWindow(StrEnum):
    TODAY = "today"
    TOMORROW = "tomorrow"
    THIS_WEEK = "this_week"
    NEXT_WEEK = "next_week"
    NEXT_7_DAYS = "next_7_days"
    THIS_MONTH = "this_month"
    NEXT_MONTH = "next_month"
    OVERDUE = "overdue"
    UPCOMING = "upcoming"


class DeadlineService:
    """Translate human calendar windows into UTC persistence queries."""

    def __init__(
        self,
        repository: AssignmentRepository,
        *,
        academic_timezone: ZoneInfo,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._timezone = academic_timezone
        self._clock = clock or (lambda: datetime.now(UTC))

    def query(
        self,
        window: DeadlineWindow,
        *,
        canvas_course_id: str | None = None,
    ) -> list[Assignment]:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("deadline clock must return a timezone-aware datetime")
        local_now = now.astimezone(self._timezone)
        lower, upper = self._bounds(window, local_now)
        return self._repository.query_due(
            lower=lower.astimezone(UTC) if lower else None,
            upper=upper.astimezone(UTC) if upper else None,
            canvas_course_id=canvas_course_id,
        )

    def _bounds(
        self,
        window: DeadlineWindow,
        local_now: datetime,
    ) -> tuple[datetime | None, datetime | None]:
        start_today = datetime.combine(local_now.date(), time.min, self._timezone)
        if window is DeadlineWindow.TODAY:
            return start_today, start_today + timedelta(days=1)
        if window is DeadlineWindow.TOMORROW:
            start_tomorrow = start_today + timedelta(days=1)
            return start_tomorrow, start_tomorrow + timedelta(days=1)
        if window is DeadlineWindow.THIS_WEEK:
            start_week = start_today - timedelta(days=start_today.weekday())
            return start_week, start_week + timedelta(days=7)
        if window is DeadlineWindow.NEXT_WEEK:
            start_week = start_today - timedelta(days=start_today.weekday())
            start_next_week = start_week + timedelta(days=7)
            return start_next_week, start_next_week + timedelta(days=7)
        if window is DeadlineWindow.NEXT_7_DAYS:
            return local_now, local_now + timedelta(days=7)
        if window is DeadlineWindow.THIS_MONTH:
            start_month = start_today.replace(day=1)
            return start_month, _next_month(start_month)
        if window is DeadlineWindow.NEXT_MONTH:
            start_next_month = _next_month(start_today.replace(day=1))
            return start_next_month, _next_month(start_next_month)
        if window is DeadlineWindow.OVERDUE:
            return None, local_now
        if window is DeadlineWindow.UPCOMING:
            return local_now, None
        raise ValueError(f"Unsupported deadline window: {window}")

    def query_month(
        self,
        year: int,
        month: int,
        *,
        canvas_course_id: str | None = None,
    ) -> list[Assignment]:
        if not 1 <= month <= 12 or not 1970 <= year <= 9999:
            raise ValueError("calendar month is invalid")
        lower = datetime(year, month, 1, tzinfo=self._timezone)
        upper = _next_month(lower)
        return self._repository.query_due(
            lower=lower.astimezone(UTC),
            upper=upper.astimezone(UTC),
            canvas_course_id=canvas_course_id,
        )

    def normalized_window(
        self,
        window: DeadlineWindow | str,
        *,
        clock_now: datetime | None = None,
    ) -> str:
        now = clock_now or self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            now = now.replace(tzinfo=UTC)
        local_now = now.astimezone(self._timezone)

        if isinstance(window, str) and "/" in window and len(window) >= 10:
            return window

        if window == DeadlineWindow.TODAY or window == "today":
            return local_now.strftime("%Y-%m-%d")
        if window == DeadlineWindow.TOMORROW or window == "tomorrow":
            return (local_now + timedelta(days=1)).strftime("%Y-%m-%d")
        if window == DeadlineWindow.THIS_WEEK or window == "this_week":
            start_week = local_now.date() - timedelta(days=local_now.weekday())
            end_week = start_week + timedelta(days=6)
            return f"{start_week.strftime('%Y-%m-%d')}/{end_week.strftime('%Y-%m-%d')}"
        if window == DeadlineWindow.NEXT_WEEK or window == "next_week":
            start_week = local_now.date() - timedelta(days=local_now.weekday()) + timedelta(days=7)
            end_week = start_week + timedelta(days=6)
            return f"{start_week.strftime('%Y-%m-%d')}/{end_week.strftime('%Y-%m-%d')}"
        if window == DeadlineWindow.THIS_MONTH or window == "this_month":
            start_month = local_now.date().replace(day=1)
            next_month = _next_month(datetime(local_now.year, local_now.month, 1)).date()
            end_month = next_month - timedelta(days=1)
            return f"{start_month.strftime('%Y-%m-%d')}/{end_month.strftime('%Y-%m-%d')}"
        if window == DeadlineWindow.NEXT_7_DAYS or window == "next_7_days":
            end_7 = local_now.date() + timedelta(days=7)
            return f"{local_now.strftime('%Y-%m-%d')}/{end_7.strftime('%Y-%m-%d')}"
        return local_now.strftime("%Y-%m-%d")


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)

