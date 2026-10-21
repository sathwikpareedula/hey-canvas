from datetime import UTC, datetime

from app.courses.models import CourseSnapshot
from app.database.course_repository import CourseRepository
from app.practice_sessions.models import PracticeAnswer, PracticeSessionCreate
from app.practice_sessions.service import PracticeSessionService
from app.services.study_context import StudyContextService
from app.study_guides.models import StudyGuideRequest
from app.study_guides.service import StudyGuideService
from app.study_sessions.models import StudySessionCreate, StudySessionProgress
from app.study_sessions.service import StudySessionService


def test_structured_study_session_progress_and_continuation(session) -> None:
    service = StudySessionService(session)
    created = service.create(
        StudySessionCreate(
            course_id="course-1",
            goal="Prepare for the midterm",
            duration_minutes=45,
            topics=("kinematics", "forces"),
            study_mode="exam_prep",
        )
    )
    assert created.progress == 0
    advanced = service.advance(
        created.session_id,
        StudySessionProgress(completed_step=1),
    )
    assert advanced.progress > 0
    assert service.continue_session(created.session_id).status == "active"


def test_study_progress_refreshes_durable_context(session) -> None:
    CourseRepository(session).synchronize(
        [
            CourseSnapshot(
                canvas_course_id="course-1",
                course_name="Course",
                workflow_state="available",
                enrollment_state="active",
            )
        ],
        synced_at=datetime.now(UTC),
    )
    session.commit()
    service = StudySessionService(session)
    created = service.create(
        StudySessionCreate(
            course_id="course-1",
            goal="Review",
            duration_minutes=30,
            topics=("limits",),
        )
    )
    service.advance(created.session_id, StudySessionProgress(completed_step=1))
    context = StudyContextService(session).get("course-1")
    assert context is not None
    assert context.starting_point == f"study_session:{created.session_id}"
    assert context.study_note == "Progress: 33%"


def test_practice_session_question_hint_answer_and_progress(session) -> None:
    service = PracticeSessionService(session)
    created = service.create(
        PracticeSessionCreate(course_id="course-1", topic="forces", total_questions=2)
    )
    assert created.question is not None
    assert "Hint:" in service.hint(created.session_id).hint
    feedback = service.answer(
        created.session_id,
        PracticeAnswer(answer="A force changes motion by producing acceleration over time."),
    )
    assert feedback.correct
    assert feedback.next_question is not None
    assert service.get(created.session_id).question_index == 1


def test_study_guide_marks_missing_evidence_without_inventing_requirements() -> None:
    guide = StudyGuideService().build(
        StudyGuideRequest(course_id="course-1", topic="exam review")
    )
    assert guide.uncertainties
    assert guide.evidence == ()
    assert all("requirement" not in item.lower() for item in guide.explanations)
