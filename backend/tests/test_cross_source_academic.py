"""Cross-source academic intelligence: current coverage and release blockers."""

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.assistant_orchestration.models import AssistantOperation
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_tools.models import AssistantRequest


def test_canvas_announcements_table_exists(session: Session) -> None:
    inspector = inspect(session.get_bind())
    table_names = {name.casefold() for name in inspector.get_table_names()}
    assert "canvas_announcements" in table_names
    assert "course_syllabi" in table_names


def test_quiz_teach_query_routes_to_assignment_context() -> None:
    request = AssistantRequest(
        query="When is Quiz 3, what topics are covered, and teach me everything I need?",
        course_id="278791",
    )
    operation = AcademicAssistantOrchestrator._operation_for(request)
    assert operation is AssistantOperation.ASSIGNMENT_CONTEXT
