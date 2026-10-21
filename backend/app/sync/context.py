"""Process-local context used to associate transactional change events to one sync run."""

from contextvars import ContextVar, Token

_sync_run_id: ContextVar[int | None] = ContextVar("sync_run_id", default=None)


def current_sync_run_id() -> int | None:
    return _sync_run_id.get()


def set_sync_run_id(run_id: int) -> Token[int | None]:
    return _sync_run_id.set(run_id)


def reset_sync_run_id(token: Token[int | None]) -> None:
    _sync_run_id.reset(token)
