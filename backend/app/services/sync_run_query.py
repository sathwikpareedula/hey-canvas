"""Local-only persisted synchronization run queries."""

from sqlalchemy.orm import Session

from app.database.sync_run_repository import SyncRunRepository
from app.sync.models import SyncRunStatus, SyncRunView


class SyncRunQueryService:
    def __init__(self, session: Session) -> None:
        self._repository = SyncRunRepository(session)

    def list_runs(
        self, *, status: SyncRunStatus | None = None, limit: int = 50
    ) -> list[SyncRunView]:
        return self._repository.views(status=status, limit=limit)

    def get(self, run_id: int) -> SyncRunView | None:
        item = self._repository.get(run_id)
        return SyncRunView.model_validate(item) if item is not None else None
