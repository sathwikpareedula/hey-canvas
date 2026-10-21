"""Persistence and overlap control for unified synchronization runs."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import SyncRun
from app.sync.models import SyncRunError, SyncRunResult, SyncRunStatus, SyncRunView

MAX_STORED_ERRORS = 100
LOCK_KEY = "canvas-sync-all"


class SyncAlreadyRunningError(RuntimeError):
    """A fresh local unified sync lease already exists."""


class SyncRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def begin(
        self,
        *,
        started_at: datetime,
        trigger: str,
        course_ids: list[str],
        check_local_files: bool,
        stale_after: timedelta,
    ) -> SyncRun:
        _require_aware(started_at)
        cutoff = started_at - stale_after
        running = list(
            self._session.scalars(select(SyncRun).where(SyncRun.status == "running"))
        )
        for item in running:
            if item.heartbeat_at < cutoff:
                item.status = "interrupted"
                item.finished_at = started_at
                item.active_lock_key = None
                item.error_count += 1
                item.errors = _bounded_errors(
                    item.errors,
                    SyncRunError(
                        stage="orchestrator",
                        error_type="InterruptedRun",
                        message="Previous sync run was abandoned after its lease became stale",
                    ),
                )
            else:
                raise SyncAlreadyRunningError("A unified Canvas synchronization is already running")
        run = SyncRun(
            started_at=started_at,
            finished_at=None,
            heartbeat_at=started_at,
            status="running",
            trigger=trigger,
            scope_course_ids=course_ids,
            check_local_files=check_local_files,
            active_lock_key=LOCK_KEY,
            stage_results={},
            change_summary={},
            change_events_created=0,
            error_count=0,
            errors=[],
            created_at=started_at,
        )
        self._session.add(run)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise SyncAlreadyRunningError(
                "A unified Canvas synchronization is already running"
            ) from exc
        return run

    def heartbeat(self, run: SyncRun, *, at: datetime) -> None:
        _require_aware(at)
        run.heartbeat_at = at
        self._session.commit()

    def finish(self, run: SyncRun, result: SyncRunResult) -> None:
        run.status = result.status
        run.finished_at = result.finished_at
        run.heartbeat_at = result.finished_at or result.started_at
        run.active_lock_key = None
        run.stage_results = {
            key: value.model_dump(mode="json") for key, value in result.stages.items()
        }
        run.change_summary = dict(result.changes)
        run.change_events_created = result.change_events_created
        run.error_count = len(result.errors)
        run.errors = [error.model_dump(mode="json") for error in result.errors[:MAX_STORED_ERRORS]]
        self._session.commit()

    def add_error(self, run: SyncRun, error: SyncRunError) -> None:
        run.errors = _bounded_errors(run.errors, error)
        run.error_count = min(run.error_count + 1, MAX_STORED_ERRORS)

    def list_runs(
        self, *, status: SyncRunStatus | None = None, limit: int = 50
    ) -> list[SyncRun]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        statement = select(SyncRun)
        if status is not None:
            statement = statement.where(SyncRun.status == status)
        statement = statement.order_by(SyncRun.started_at.desc(), SyncRun.id.desc()).limit(limit)
        return list(self._session.scalars(statement))

    def get(self, run_id: int) -> SyncRun | None:
        return self._session.get(SyncRun, run_id)

    def views(self, **filters: Any) -> list[SyncRunView]:
        return [SyncRunView.model_validate(item) for item in self.list_runs(**filters)]


def _bounded_errors(existing: list[dict[str, Any]], error: SyncRunError) -> list[dict[str, Any]]:
    if len(existing) >= MAX_STORED_ERRORS:
        return list(existing)
    return [*existing, error.model_dump(mode="json")]


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("sync run timestamps must be timezone-aware")
