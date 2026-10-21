from datetime import UTC, datetime

from app.database.models import Base
from app.database.session import (
    _backfill_course_material_references,
    _ensure_sqlite_compatibility_columns,
)
from sqlalchemy import create_engine, inspect, text


def test_new_tables_are_added_without_losing_pre_feature_records(database_engine):
    new_table_names = {
        "notification_records",
        "reminder_preferences",
        "calendar_links",
        "calendar_actions",
        "study_sessions",
        "practice_sessions",
        "practice_turns",
    }
    legacy_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in new_table_names
    ]
    Base.metadata.create_all(database_engine, tables=legacy_tables)

    now = datetime.now(UTC).isoformat()
    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO courses (
                    canvas_course_id, course_code, course_name,
                    first_seen_at, last_seen_at, last_synced_at
                ) VALUES (
                    :course_id, :course_code, :course_name,
                    :first_seen_at, :last_seen_at, :last_synced_at
                )
                """
            ),
            {
                "course_id": "legacy-course",
                "course_code": "LEG 101",
                "course_name": "Legacy Course",
                "first_seen_at": now,
                "last_seen_at": now,
                "last_synced_at": now,
            },
        )

    Base.metadata.create_all(database_engine)

    tables = set(inspect(database_engine).get_table_names())
    assert new_table_names <= tables
    with database_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT canvas_course_id, course_name FROM courses "
                "WHERE canvas_course_id = :course_id"
            ),
            {"course_id": "legacy-course"},
        ).one()
    assert row == ("legacy-course", "Legacy Course")


def test_practice_question_identity_column_is_added_non_destructively(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-practice.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE practice_turns ("
                "id INTEGER PRIMARY KEY, session_id VARCHAR(255), "
                "question_index INTEGER, question VARCHAR(2000))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO practice_turns "
                "(session_id, question_index, question) VALUES ('practice:legacy', 0, 'Legacy')"
            )
        )

    _ensure_sqlite_compatibility_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("practice_turns")}
    assert "question_id" in columns
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT session_id, question FROM practice_turns WHERE id = 1")
        ).one()
    assert row == ("practice:legacy", "Legacy")
    engine.dispose()


def test_existing_module_file_relationships_backfill_explicit_ownership(
    database_engine,
) -> None:
    Base.metadata.create_all(database_engine)
    now = datetime.now(UTC).isoformat()
    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO courses (
                    canvas_course_id, first_seen_at, last_seen_at, last_synced_at
                ) VALUES (:course_id, :now, :now, :now)
                """
            ),
            {"course_id": "legacy-owner", "now": now},
        )
        course_id = connection.execute(
            text("SELECT id FROM courses WHERE canvas_course_id = 'legacy-owner'")
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO modules (
                    course_id, canvas_module_id, prerequisite_module_ids,
                    first_seen_at, last_seen_at, last_synced_at
                ) VALUES (:course_id, 'module-1', '[]', :now, :now, :now)
                """
            ),
            {"course_id": course_id, "now": now},
        )
        module_id = connection.execute(
            text("SELECT id FROM modules WHERE canvas_module_id = 'module-1'")
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO module_items (
                    course_id, module_id, canvas_module_item_id,
                    item_type, content_id, first_seen_at, last_seen_at, last_synced_at
                ) VALUES (:course_id, :module_id, 'item-1', 'File',
                          'file-1', :now, :now, :now)
                """
            ),
            {"course_id": course_id, "module_id": module_id, "now": now},
        )
        connection.execute(
            text(
                """
                INSERT INTO canvas_files (
                    canvas_file_id, metadata_fingerprint,
                    first_seen_at, last_seen_at, last_synced_at, download_state
                ) VALUES ('file-1', 'fingerprint', :now, :now, :now, 'not_downloaded')
                """
            ),
            {"now": now},
        )

    _backfill_course_material_references(database_engine)
    with database_engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT course_id FROM course_material_references "
                "WHERE canvas_file_id = 'file-1'"
            )
        ).scalar_one() == "legacy-owner"
