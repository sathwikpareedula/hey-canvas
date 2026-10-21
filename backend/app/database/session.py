"""SQLAlchemy engine and session factory management."""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine, event, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Base, SchemaVersion


def _ensure_sqlite_parent_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    parsed = urlparse(database_url)
    if parsed.scheme not in {"sqlite"}:
        return
    raw_path = parsed.path
    if raw_path in {":memory:", ""}:
        return
    if raw_path.startswith("/./"):
        raw_path = raw_path.removeprefix("/./")
    elif (
        raw_path.startswith("/")
        and len(raw_path) > 3
        and raw_path[1].isalpha()
        and raw_path[2] == ":"
    ):
        raw_path = raw_path[1:]

    sqlite_path = Path(raw_path)
    parent = sqlite_path.resolve().parent if not sqlite_path.is_absolute() else sqlite_path.parent
    if parent.exists() or str(parent) in {".", ""}:
        return
    parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    _ensure_sqlite_parent_directory(settings.database_url)
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    engine = create_engine(settings.database_url, connect_args=connect_args)
    if settings.database_url.startswith("sqlite"):
        enable_sqlite_foreign_keys(engine)
    return engine


def enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Enforce declared foreign keys on every SQLite connection."""

    event.listen(engine, "connect", _set_sqlite_foreign_keys)


def _set_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def initialize_database() -> None:
    """Create registered tables and record a non-destructive schema version."""

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compatibility_columns(engine)
    _backfill_course_material_references(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        if session.scalar(select(SchemaVersion).where(SchemaVersion.version == 1)) is None:
            session.add(SchemaVersion(version=1, applied_at=datetime.now(UTC)))
            session.commit()


def _ensure_sqlite_compatibility_columns(engine: Engine) -> None:
    """Apply the small, explicit SQLite compatibility upgrades owned by this app."""

    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "practice_turns" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("practice_turns")}
    if "question_id" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE practice_turns ADD COLUMN question_id VARCHAR(255)")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_practice_turns_question_id "
                "ON practice_turns (question_id)"
            )
        )


def _backfill_course_material_references(engine: Engine) -> None:
    """Backfill explicit file/course ownership from normalized module-item facts."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT OR IGNORE INTO course_material_references
                    (course_id, canvas_file_id, source_module_item_id,
                     first_seen_at, last_seen_at)
                SELECT c.canvas_course_id, mi.content_id, mi.canvas_module_item_id,
                       c.last_synced_at, c.last_synced_at
                FROM module_items mi
                JOIN courses c ON c.id = mi.course_id
                WHERE mi.item_type = 'File' AND mi.content_id IS NOT NULL
                """
            )
        )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the configured session factory."""

    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a short-lived database session for FastAPI dependencies."""

    with get_session_factory()() as session:
        yield session
