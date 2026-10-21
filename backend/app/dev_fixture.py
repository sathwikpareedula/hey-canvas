"""Deterministic synthetic academic fixture for local Hey Canvas demos."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.models import (
    AcademicDocument,
    Assignment,
    Base,
    CanvasFile,
    ChangeEvent,
    Course,
    CourseMaterialReference,
    CourseModule,
    DocumentUnit,
    ModuleItem,
    StudyContext,
)
from app.database.session import _ensure_sqlite_compatibility_columns, enable_sqlite_foreign_keys
from app.notifications.service import NotificationService

SYNTHETIC_PREFIX = "synthetic-"


@dataclass(frozen=True)
class FixtureSummary:
    courses: int
    assignments: int
    modules: int
    documents: int
    document_units: int
    changes: int
    notifications: int
    already_seeded: bool


def seed_synthetic_fixture(database_path: Path, *, now: datetime | None = None) -> FixtureSummary:
    """Populate a dedicated SQLite file with bounded, clearly synthetic data."""

    target = database_path.resolve()
    if target.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("synthetic fixture database must be a SQLite file")
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{target.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    _ensure_sqlite_compatibility_columns(engine)
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("fixture clock must be timezone-aware")

    try:
        with Session(engine, expire_on_commit=False) as session:
            non_synthetic = session.scalar(
                select(Course).where(~Course.canvas_course_id.startswith(SYNTHETIC_PREFIX)).limit(1)
            )
            if non_synthetic is not None:
                raise ValueError("refusing to seed a database containing non-synthetic courses")
            existing = session.scalar(
                select(Course).where(Course.canvas_course_id == "synthetic-robotics")
            )
            if existing is not None:
                return _summary(session, already_seeded=True)
            _populate(session, observed_at)
            return _summary(session, already_seeded=False)
    finally:
        engine.dispose()


def _populate(session: Session, now: datetime) -> None:
    local_zone = ZoneInfo("America/Chicago")
    local_now = now.astimezone(local_zone)
    today_due = datetime.combine(local_now.date(), time(23, 0), tzinfo=local_zone).astimezone(UTC)
    tomorrow_due = datetime.combine(
        local_now.date() + timedelta(days=1), time(17, 0), tzinfo=local_zone
    ).astimezone(UTC)

    robotics = _course(
        "synthetic-robotics",
        "CSE 4360",
        "Synthetic Autonomous Robots",
        now,
    )
    neural = _course(
        "synthetic-neural-networks",
        "CSE 4309",
        "Synthetic Neural Networks",
        now,
    )
    session.add_all((robotics, neural))
    session.flush()

    assignments = (
        _assignment(robotics, "synthetic-assignment-today", "Kinematics Worksheet", today_due, now),
        _assignment(
            robotics,
            "synthetic-assignment-tomorrow",
            "Robot Planning Quiz",
            tomorrow_due,
            now,
        ),
        _assignment(
            neural,
            "synthetic-assignment-future",
            "Gradient Descent Project",
            now + timedelta(days=5),
            now,
        ),
        _assignment(
            neural,
            "synthetic-assignment-overdue",
            "Perceptron Reflection",
            now - timedelta(days=1),
            now,
        ),
    )
    session.add_all(assignments)

    module = CourseModule(
        course=robotics,
        canvas_module_id="synthetic-module-kinematics",
        name="Kinematics and Motion",
        position=1,
        prerequisite_module_ids=[],
        workflow_state="active",
        state="unlocked",
        items_count=2,
        published=True,
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    session.add(module)
    session.flush()

    file_specs = (
        (
            "synthetic-file-robotics-pdf",
            "Synthetic Kinematics Notes.pdf",
            "application/pdf",
            "pdf",
            "page",
            1,
            None,
            "Forward Kinematics",
            (
                "Forward Kinematics for a Two-Link Planar Arm:\n\n"
                "Forward kinematics determines the Cartesian position (x, y) of the "
                "end-effector from joint angles (theta_1, theta_2) and link lengths (L1, L2).\n\n"
                "Planar Arm Geometry:\n"
                "• Base frame is at origin (0, 0).\n"
                "• Link 1 has length L1 and rotates by joint angle theta_1 relative to "
                "the positive x-axis.\n"
                "• Link 2 has length L2 and rotates by relative joint angle theta_2 "
                "with respect to Link 1.\n"
                "• The total orientation of Link 2 in the base coordinate frame is "
                "(theta_1 + theta_2).\n\n"
                "Kinematics Equations:\n"
                "• x = L1 * cos(theta_1) + L2 * cos(theta_1 + theta_2)\n"
                "• y = L1 * sin(theta_1) + L2 * sin(theta_1 + theta_2)\n\n"
                "Worked Example:\n"
                "Given L1 = 10 cm, L2 = 5 cm, theta_1 = 0 rad (0 deg), "
                "theta_2 = pi/2 rad (90 deg):\n"
                "x = 10 * cos(0) + 5 * cos(90) = 10 * 1 + 5 * 0 = 10 cm\n"
                "y = 10 * sin(0) + 5 * sin(90) = 10 * 0 + 5 * 1 = 5 cm\n"
                "The end-effector position is (x, y) = (10, 5) cm."
            ),
        ),
        (
            "synthetic-file-robotics-slides",
            "Synthetic Motion Planning.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "pptx",
            "slide",
            None,
            1,
            "Motion Planning",
            "Synthetic slide material compares configuration spaces and collision-free paths.",
        ),
    )
    for index, spec in enumerate(file_specs, start=1):
        file_id, filename, content_type, parser, unit_type, page, slide, heading, text_value = spec
        digest = hashlib.sha256(text_value.encode()).hexdigest()
        canvas_file = CanvasFile(
            canvas_file_id=file_id,
            display_name=filename,
            filename=filename,
            content_type=content_type,
            size=len(text_value.encode()),
            metadata_fingerprint=hashlib.sha256(filename.encode()).hexdigest(),
            downloaded_metadata_fingerprint=hashlib.sha256(filename.encode()).hexdigest(),
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
            sha256=digest,
            local_size=len(text_value.encode()),
            download_state="downloaded",
        )
        session.add(canvas_file)
        session.add(
            CourseMaterialReference(
                course_id=robotics.canvas_course_id,
                canvas_file_id=file_id,
                source_module_item_id=f"synthetic-module-item-{index}",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        session.flush()
        module.items.append(
            ModuleItem(
                course=robotics,
                canvas_module_item_id=f"synthetic-module-item-{index}",
                title=filename,
                position=index,
                item_type="File",
                content_id=file_id,
                indent=0,
                published=True,
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
        )
        document = AcademicDocument(
            canvas_file_id=file_id,
            detected_type=parser,
            status="parsed",
            parser_name=parser,
            parser_version="synthetic-v1",
            source_sha256=digest,
            parsed_at=now,
            unit_count=1,
            character_count=len(text_value),
            last_attempted_at=now,
            last_attempt_source_sha256=digest,
            last_attempt_parser_version="synthetic-v1",
            last_attempt_status="parsed",
            created_at=now,
            updated_at=now,
        )
        document.units.append(
            DocumentUnit(
                unit_type=unit_type,
                unit_index=0,
                page_number=page,
                slide_number=slide,
                heading=heading,
                text=text_value,
                text_fingerprint=hashlib.sha256(text_value.encode()).hexdigest(),
                character_count=len(text_value),
            )
        )
        session.add(document)

    session.add(
        ChangeEvent(
            entity_type="assignment",
            entity_external_id="synthetic-assignment-tomorrow",
            course_canvas_id=robotics.canvas_course_id,
            event_type="field_changed",
            field_name="due_at",
            old_value=(tomorrow_due - timedelta(days=1)).isoformat(),
            new_value=tomorrow_due.isoformat(),
            observed_at=now,
            source="synthetic_fixture",
            context={"synthetic": True},
            created_at=now,
        )
    )
    session.add(
        StudyContext(
            course_id=robotics.canvas_course_id,
            current_topic="forward kinematics",
            assignment_id="synthetic-assignment-tomorrow",
            study_mode="balanced",
            starting_point="synthetic_demo",
            concepts_covered=["coordinate frames"],
            topics_to_revisit=["homogeneous transforms"],
            study_note="Synthetic local demo context.",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    NotificationService(session, clock=lambda: now).list_notifications()


def _course(course_id: str, code: str, name: str, now: datetime) -> Course:
    return Course(
        canvas_course_id=course_id,
        course_code=code,
        course_name=name,
        term_canvas_id="synthetic-fall-2026",
        term_name="Synthetic Fall 2026",
        workflow_state="available",
        enrollment_state="active",
        enrollment_type="StudentEnrollment",
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )


def _assignment(
    course: Course,
    assignment_id: str,
    name: str,
    due_at: datetime,
    now: datetime,
) -> Assignment:
    return Assignment(
        course=course,
        canvas_assignment_id=assignment_id,
        name=name,
        description_html="<p>Synthetic assignment content for local validation only.</p>",
        due_at=due_at,
        points_possible=100,
        submission_types=["online_upload"],
        workflow_state="published",
        published=True,
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )


def _summary(session: Session, *, already_seeded: bool) -> FixtureSummary:
    courses = list(session.scalars(select(Course)))
    assignments = list(session.scalars(select(Assignment)))
    modules = list(session.scalars(select(CourseModule)))
    documents = list(session.scalars(select(AcademicDocument)))
    units = list(session.scalars(select(DocumentUnit)))
    changes = list(session.scalars(select(ChangeEvent)))
    notifications = NotificationService(session).list_notifications().total
    return FixtureSummary(
        courses=len(courses),
        assignments=len(assignments),
        modules=len(modules),
        documents=len(documents),
        document_units=len(units),
        changes=len(changes),
        notifications=notifications,
        already_seeded=already_seeded,
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Seed a dedicated synthetic Hey Canvas SQLite DB")
    parser.add_argument("--database-path", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(asdict(seed_synthetic_fixture(args.database_path)), sort_keys=True))


if __name__ == "__main__":
    run()
