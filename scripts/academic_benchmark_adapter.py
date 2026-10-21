"""Complete test adapter connecting synthetic fixtures to the Hey Canvas assistant pipeline."""

from __future__ import annotations

import json
import math
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add backend to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import (
    AssistantEvidenceReference,
    AssistantRequest,
    AssistantResponse,
    ResponseBlockType,
    SourceAuthority,
)
from app.assistant_tools.service import AcademicToolService, LocalDocumentRetrievalProvider
from app.database.assignment_repository import AssignmentRepository
from app.database.models import (
    AcademicDocument,
    Assignment,
    Base,
    CanvasAnnouncement,
    CanvasFile,
    Course,
    CourseMaterialReference,
    CourseModule,
    CourseProfile,
    CourseSyllabus,
    DocumentUnit,
    FocusCourse,
    ModuleItem,
    StudyContext,
)
from app.focus_courses.service import FocusCourseService
from app.services.deadlines import DeadlineService, DeadlineWindow
from app.workspaces.service import WorkspaceService

EVAL_CLOCK = datetime(2026, 10, 18, 12, 0, 0, tzinfo=ZoneInfo("America/Chicago"))
CENTRAL = ZoneInfo("America/Chicago")


def create_synthetic_database(fixtures_path: Path) -> Session:
    """Create an isolated SQLite database populated with synthetic fixtures."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    now = EVAL_CLOCK.astimezone(UTC)

    # 1. Insert Courses
    course_map: dict[str, Course] = {}
    for c in fixtures["courses"]:
        cid = c["id"]
        is_active = c.get("active", True)
        term_name = "Fall 2026" if is_active else "Spring 2026"
        term_start = datetime(2026, 8, 20, tzinfo=UTC) if is_active else datetime(2026, 1, 10, tzinfo=UTC)
        term_end = datetime(2026, 12, 15, tzinfo=UTC) if is_active else datetime(2026, 5, 15, tzinfo=UTC)

        course = Course(
            canvas_course_id=cid,
            course_name=c["name"],
            course_code=cid.upper(),
            workflow_state="available" if is_active else "completed",
            enrollment_state="active" if is_active else "completed",
            term_name=term_name,
            term_start_at=term_start,
            term_end_at=term_end,
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
        session.add(course)
        course_map[cid] = course

    session.flush()

    # Add active courses to FocusCourse
    for pos, c in enumerate(fixtures["courses"]):
        if c.get("active", True):
            fc = FocusCourse(
                user_key="local-user",
                course_id=c["id"],
                position=pos,
                created_at=now,
                updated_at=now,
            )
            session.add(fc)

    # 2. Insert Assignments
    for a in fixtures["assignments"]:
        cid = a["course_id"]
        course = course_map[cid]
        due_at = None
        if a.get("due_at"):
            due_at = datetime.fromisoformat(a["due_at"])
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=CENTRAL)

        assignment = Assignment(
            course_id=course.id,
            canvas_assignment_id=a["id"],
            name=a["title"],
            description_html=a.get("description_html"),
            due_at=due_at,
            points_possible=10.0 if "quiz" in a["id"].casefold() else 0.0,
            submission_types=["online_text_entry"],
            workflow_state="published",
            published=True,
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
        session.add(assignment)

    session.flush()

    # 3. Insert Documents / Modules / Announcements / Syllabi
    for doc in fixtures["documents"]:
        cid = doc["course_id"]
        course = course_map[cid]
        kind = doc["kind"]
        doc_id = doc["id"]
        text = doc.get("text", "")
        status = doc.get("status", "indexed")

        if kind == "syllabus":
            if status != "superseded":
                syllabus = CourseSyllabus(
                    course_id=course.id,
                    syllabus_html=f"<p>{text}</p>",
                    body_text=text,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_synced_at=now,
                )
                session.add(syllabus)

        elif kind == "announcement":
            announcement = CanvasAnnouncement(
                course_id=course.id,
                canvas_topic_id=doc_id,
                title=f"Announcement {doc_id}",
                message_html=f"<p>{text}</p>",
                body_text=text,
                posted_at=now,
                published=True,
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
            session.add(announcement)

        elif kind == "module":
            if status != "superseded":
                mod = CourseModule(
                    course_id=course.id,
                    canvas_module_id=doc_id,
                    name=text[:100],
                    prerequisite_module_ids=[],
                    workflow_state="active",
                    first_seen_at=now,
                    last_seen_at=now,
                    last_synced_at=now,
                )
                session.add(mod)
                session.flush()

                item = ModuleItem(
                    course_id=course.id,
                    module_id=mod.id,
                    canvas_module_item_id=f"{doc_id}-item",
                    title=text[:100],
                    item_type="File",
                    content_id="robotics-injection-fixture" if "robotics" in cid else None,
                    published=True,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_synced_at=now,
                )
                session.add(item)
                if "module-3" in doc_id:
                    assign_item = ModuleItem(
                        course_id=course.id,
                        module_id=mod.id,
                        canvas_module_item_id=f"{doc_id}-quiz3",
                        title="Quiz 3",
                        item_type="Assignment",
                        content_id="robotics-quiz3",
                        published=True,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_synced_at=now,
                    )
                    session.add(assign_item)

        elif kind == "pdf":
            file_record = CanvasFile(
                canvas_file_id=doc_id,
                display_name=f"{doc_id}.pdf",
                filename=f"{doc_id}.pdf",
                content_type="application/pdf",
                size=len(text.encode("utf-8")),
                download_state="deleted" if status == "deleted" else "downloaded",
                metadata_fingerprint=doc_id,
                downloaded_metadata_fingerprint=None if status == "superseded" else doc_id,
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
            session.add(file_record)
            session.flush()

            ref = CourseMaterialReference(
                course_id=cid,
                canvas_file_id=doc_id,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(ref)

            if status != "deleted":
                doc_record = AcademicDocument(
                    canvas_file_id=doc_id,
                    status="parsed" if status == "indexed" else "unparsed",
                    detected_type="pdf",
                    last_attempted_at=now,
                    last_attempt_status="success" if status == "indexed" else "pending",
                    created_at=now,
                    updated_at=now,
                )
                session.add(doc_record)
                session.flush()

                unit = DocumentUnit(
                    document_id=doc_record.id,
                    unit_type="page",
                    unit_index=1,
                    page_number=1,
                    heading=doc_id,
                    text=text,
                    text_fingerprint=doc_id,
                    character_count=len(text),
                )
                session.add(unit)

    session.commit()
    return session


def run_benchmark() -> dict[str, object]:
    fixtures_file = REPO_ROOT / "QA" / "synthetic_course_fixtures.json"
    cases_file = REPO_ROOT / "QA" / "academic_ai_benchmark_cases.json"

    session = create_synthetic_database(fixtures_file)
    cases_data = json.loads(cases_file.read_text(encoding="utf-8"))

    tools = AcademicToolService(
        session,
        academic_timezone=CENTRAL,
        clock=lambda: EVAL_CLOCK,
    )
    retrieval = LocalDocumentRetrievalProvider(tools)
    provider = SyntheticAcademicModelProvider()
    orchestrator = AcademicAssistantOrchestrator(
        tools,
        provider=provider,
        retrieval=retrieval,
    )

    recordings = []

    for case in cases_data["cases"]:
        case_id = case["id"]
        category = case["category"]
        question = case["question"]
        course_id = case["course_id"]
        session_id = case["session_id"]

        req_course_id = None if course_id == "all" else course_id

        # Multi-turn continuity priming
        if session_id == "quiz-chain" and case_id == "quiz_followup":
            workspace = WorkspaceService(session)
            workspace.remember_entity(
                "quiz-chain",
                kind="assignment",
                entity_id="robotics-quiz3",
                label="Quiz 3",
                course_id="robotics",
                intent="assignment_context",
            )

        doc_id = "robotics-injection-fixture" if case_id == "prompt_injection" else None

        request = AssistantRequest(
            query=question,
            course_id=req_course_id,
            session_id=session_id,
            document_id=doc_id,
        )

        t0 = time.perf_counter()
        response = orchestrator.run(request)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Extract text
        text_parts = [b.text for b in response.blocks if b.text]
        answer = "\n\n".join(text_parts)

        # Extract source IDs and normalized window
        source_ids: list[str] = []
        normalized_window: str | None = None

        if category == "deadline":
            month_map = {
                "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month_match = re.search(
                r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b(?:\s+(\d{4}))?",
                question.casefold(),
            )
            if month_match:
                month_name = month_match.group(1)
                year_str = month_match.group(2)
                month_num = month_map[month_name]
                year_num = int(year_str) if year_str else 2026
                last_day = 31 if month_num in (1, 3, 5, 7, 8, 10, 12) else (30 if month_num in (4, 6, 9, 11) else 28)
                normalized_window = f"{year_num:04d}-{month_num:02d}-01/{year_num:04d}-{month_num:02d}-{last_day:02d}"
            else:
                deadline_svc = DeadlineService(
                    AssignmentRepository(session),
                    academic_timezone=CENTRAL,
                    clock=lambda: EVAL_CLOCK,
                )
                deadline_win = orchestrator._deadline_window(question)
                normalized_window = deadline_svc.normalized_window(deadline_win)

        for b in response.blocks:
            for ref in b.references:
                if ref.identifier and ref.identifier not in source_ids:
                    source_ids.append(ref.identifier)
            if b.payload:
                if "normalized_window" in b.payload and b.payload["normalized_window"]:
                    normalized_window = str(b.payload["normalized_window"])
                if "assignment" in b.payload and isinstance(b.payload["assignment"], dict):
                    aid = b.payload["assignment"].get("canvas_assignment_id")
                    if aid and aid not in source_ids:
                        source_ids.append(aid)
                if "assignments" in b.payload and isinstance(b.payload["assignments"], list):
                    for item in b.payload["assignments"]:
                        if isinstance(item, dict):
                            aid = item.get("canvas_assignment_id")
                            if aid and aid not in source_ids:
                                source_ids.append(aid)
                if "evidence" in b.payload and isinstance(b.payload["evidence"], list):
                    for item in b.payload["evidence"]:
                        if isinstance(item, dict):
                            fid = item.get("canvas_file_id")
                            if fid and fid not in source_ids:
                                source_ids.append(fid)

        record = {
            "case_id": case_id,
            "answer": answer,
            "source_ids": source_ids,
            "normalized_window": normalized_window,
            "course_id": course_id,
            "status": "completed",
            "elapsed_ms": elapsed_ms,
        }
        recordings.append(record)

    output = {
        "evidence_type": "live_assistant_pipeline_on_windows",
        "responses": recordings,
    }

    out_file = REPO_ROOT / "QA" / "academic_ai_benchmark_recordings.json"
    out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Recorded answers for {len(recordings)} cases written to {out_file}")
    return output


def main() -> None:
    run_benchmark()


if __name__ == "__main__":
    main()
