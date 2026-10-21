from datetime import UTC, datetime

from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import AssistantRequest
from app.assistant_tools.service import AcademicToolService
from app.database.announcement_repository import AnnouncementRepository
from app.database.models import Assignment, CourseModule, ModuleItem
from app.announcements.models import AnnouncementSnapshot
from app.services.cross_source_linking import extract_topics_from_text
from zoneinfo import ZoneInfo

from tests.services.test_assignment_sync import add_course


def _seed_quiz_fixture(session) -> None:
    course = add_course(session, "278791", name="Robotics")
    now = datetime.now(UTC)
    session.add(
        Assignment(
            course_id=course.id,
            canvas_assignment_id="quiz-3",
            name="Quiz 3",
            due_at=datetime(2026, 10, 20, 16, 0, tzinfo=UTC),
            submission_types=["online_quiz"],
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
    )
    module = CourseModule(
        course_id=course.id,
        canvas_module_id="mod-1",
        name="Lectures",
        prerequisite_module_ids=[],
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    session.add(module)
    session.flush()
    session.add_all(
        [
            ModuleItem(
                course_id=course.id,
                module_id=module.id,
                canvas_module_item_id="mi-quiz",
                title="Quiz 3",
                item_type="Assignment",
                content_id="quiz-3",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
            ModuleItem(
                course_id=course.id,
                module_id=module.id,
                canvas_module_item_id="mi-lec",
                title="Lecture 04 SLAM",
                item_type="File",
                content_id="file-slam",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
        ]
    )
    AnnouncementRepository(session).synchronize_course(
        course,
        [
            AnnouncementSnapshot(
                canvas_topic_id="ann-quiz3",
                canvas_course_id="278791",
                title="Quiz 3 reminder",
                message_html="<p>Quiz 3 is Oct 20. Topics: SLAM, odometry.</p>",
                posted_at=now,
            )
        ],
        synced_at=now,
    )
    session.commit()


def test_extract_topics_from_announcement_html() -> None:
    topics = extract_topics_from_text("Topics: SLAM, odometry, planning")
    assert "SLAM" in topics
    assert "odometry" in topics


def test_assignment_context_caps_retrieval_evidence(session, monkeypatch) -> None:
    _seed_quiz_fixture(session)
    from app.assistant_tools.service import AcademicToolService

    class _ManyHits:
        def evidence_for(self, *, course_id: str, query: str):
            from app.assistant_tools.models import DocumentEvidence

            return tuple(
                DocumentEvidence(
                    canvas_file_id=f"file-{index}",
                    canvas_course_id=course_id,
                    unit_type="page",
                    unit_index=0,
                    page_number=1,
                    slide_number=None,
                    heading=None,
                    excerpt=f"excerpt {index}",
                    is_stale=False,
                )
                for index in range(12)
            )

    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    context = tools.get_assignment_context(
        "quiz-3",
        course_id="278791",
        retrieval=_ManyHits(),
        retrieval_query="Quiz 3 topics",
    )
    assert context is not None
    assert len(context.retrieval_evidence) <= 8


def test_assignment_context_links_announcement_and_module_topic(session) -> None:
    _seed_quiz_fixture(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    context = tools.get_assignment_context(
        "quiz-3",
        course_id="278791",
        retrieval=None,
        retrieval_query="When is Quiz 3 and teach me the topics?",
    )
    assert context is not None
    assert context.canvas_text_evidence
    assert any("Quiz 3" in (item.title or "") for item in context.canvas_text_evidence)
    assert any(link.topic == "SLAM" for link in context.topic_module_links)


def test_course_level_announcement_reaches_model_without_assignment_context(session) -> None:
    _seed_quiz_fixture(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    orchestrator = AcademicAssistantOrchestrator(
        tools, SyntheticAcademicModelProvider(), retrieval=None
    )
    request = AssistantRequest(
        query="What did the professor announce about SLAM?",
        course_id="278791",
        operation="study_help",
    )

    model_input = orchestrator._assemble(request, orchestrator.plan(request))

    assert model_input.assignment_context is None
    assert [item.source_id for item in model_input.canvas_text_evidence] == ["ann-quiz3"]
    assert any("SLAM" in item for item in model_input.untrusted_material)
