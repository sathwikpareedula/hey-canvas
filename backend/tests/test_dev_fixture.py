from dataclasses import replace
from datetime import UTC, datetime

import pytest
from app.database.models import Base, Course
from app.dev_fixture import seed_synthetic_fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_synthetic_fixture_is_populated_and_idempotent(tmp_path) -> None:
    path = tmp_path / "hey-canvas-demo.db"
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)

    first = seed_synthetic_fixture(path, now=now)
    second = seed_synthetic_fixture(path, now=now)

    assert first.courses == 2
    assert first.assignments == 4
    assert first.modules == 1
    assert first.documents == 2
    assert first.document_units == 2
    assert first.changes == 1
    assert first.notifications >= 1
    assert first.already_seeded is False
    assert second == replace(first, already_seeded=True)


def test_synthetic_fixture_refuses_database_with_real_courses(tmp_path) -> None:
    path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    with Session(engine) as session:
        session.add(
            Course(
                canvas_course_id="real-course",
                course_name="Existing course",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
        )
        session.commit()
    engine.dispose()

    with pytest.raises(ValueError, match="non-synthetic"):
        seed_synthetic_fixture(path, now=now)
