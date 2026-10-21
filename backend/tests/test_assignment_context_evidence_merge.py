"""Regression: assignment-context retrieval must reach the model and citations."""

from app.assistant_orchestration.models import AssistantOperation, ToolPlan
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_tools.models import DocumentEvidence


def test_merge_document_evidence_dedupes_by_file_and_unit() -> None:
    first = DocumentEvidence(
        canvas_file_id="file-1",
        unit_type="page",
        unit_index=0,
        page_number=1,
        slide_number=None,
        heading=None,
        excerpt="a",
        is_stale=False,
    )
    duplicate = first.model_copy()
    second = first.model_copy(update={"unit_index": 1, "excerpt": "b"})
    merged = AcademicAssistantOrchestrator._merge_document_evidence(
        (first,),
        (duplicate, second),
    )
    assert len(merged) == 2
    assert merged[0].excerpt == "a"
    assert merged[1].excerpt == "b"


def test_canvas_text_reference_ids_include_announcement_source() -> None:
    from app.assistant_orchestration.models import AssistantModelInput
    from app.assistant_tools.models import AssistantRequest, CanvasTextEvidence

    model_input = AssistantModelInput(
        request=AssistantRequest(query="quiz", course_id="101"),
        plan=ToolPlan(
            operation=AssistantOperation.ASSIGNMENT_CONTEXT,
            course_id="101",
            query="quiz",
        ),
        context=None,
        deadlines=None,
        assignment_context=None,
        recent_changes=None,
        material_search=None,
        evidence=(),
        canvas_text_evidence=(
            CanvasTextEvidence(
                source_kind="announcement",
                canvas_course_id="101",
                source_id="topic-1",
                title="Quiz 3",
                excerpt="Topics: SLAM",
            ),
        ),
        untrusted_material=(),
        study_plan=None,
        practice_session=None,
        practice_hint=None,
        practice_feedback=None,
        study_guide=None,
        notifications=None,
        reminder_preview=None,
        calendar_preview=None,
        course_list=(),
        sync_status=None,
    )
    ids = AcademicAssistantOrchestrator._canvas_text_reference_ids(model_input)
    assert ids == {"topic-1"}
