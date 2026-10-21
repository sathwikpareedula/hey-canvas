from zoneinfo import ZoneInfo

import pytest
from app.assistant_orchestration.models import AssistantModelInput, AssistantOperation, ToolPlan
from app.documents.models import DocumentLimits
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_provider.grounded_fallback import grounded_assistant_response
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import AssistantRequest, DocumentEvidence
from app.assistant_tools.service import AcademicToolService
from app.services.retrieval_query_focus import focused_retrieval_query


@pytest.fixture
def limits() -> DocumentLimits:
    return DocumentLimits(
        max_source_bytes=5_000_000,
        max_characters=50_000,
        max_units=100,
        max_unit_characters=120,
        max_archive_entries=200,
        max_archive_uncompressed_bytes=5_000_000,
        max_archive_ratio=200,
    )


def test_focused_retrieval_query_extracts_lecture_and_topic() -> None:
    assert "lecture 01" in focused_retrieval_query(
        "How does Lecture 01 define a robot? Use course materials."
    )
    assert "robot" in focused_retrieval_query(
        "How does Lecture 01 define a robot? Use course materials."
    )


def test_grounded_fallback_requires_evidence() -> None:
    model_input = AssistantModelInput(
        request=AssistantRequest(query="robot", course_id="101"),
        plan=ToolPlan(
            operation=AssistantOperation.MATERIAL_SEARCH,
            course_id="101",
            query="robot",
        ),
        context=None,
        evidence=(),
    )
    assert grounded_assistant_response(model_input) is None


def test_grounded_fallback_builds_text() -> None:
    evidence = (
        DocumentEvidence(
            canvas_file_id="7001",
            canvas_course_id="101",
            display_name="Lecture 01.pdf",
            filename="Lecture 01.pdf",
            source_sha256="abc",
            parser_name="p",
            parser_version="1",
            unit_type="page",
            unit_index=0,
            page_number=12,
            slide_number=None,
            heading=None,
            excerpt="A robot is a machine that carries out actions.",
            is_stale=False,
            module_references=(),
            module_item_references=(),
        ),
    )
    model_input = AssistantModelInput(
        request=AssistantRequest(query="robot", course_id="101"),
        plan=ToolPlan(
            operation=AssistantOperation.MATERIAL_SEARCH,
            course_id="101",
            query="robot",
        ),
        context=None,
        evidence=evidence,
    )
    response = grounded_assistant_response(model_input)
    assert response is not None
    assert response.status == "ok"
    first_text = response.blocks[0].text or ""
    assert "Lecture 01.pdf" in first_text


class FailingProvider(SyntheticAcademicModelProvider):
    def complete(self, model_input):  # type: ignore[no-untyped-def]
        raise RuntimeError("provider request failed")


@pytest.mark.asyncio
async def test_orchestrator_falls_back_when_provider_fails(
    session, tmp_path, limits
) -> None:
    from app.retrieval.assistant_adapter import RetrievalEvidenceAdapter
    from tests.test_retrieval import seed_corpus

    await seed_corpus(session, tmp_path, limits)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    orchestrator = AcademicAssistantOrchestrator(
        tools,
        provider=FailingProvider(),
        retrieval=RetrievalEvidenceAdapter(session),
    )
    request = AssistantRequest(
        query="forward kinematics",
        course_id="101",
    )
    response = orchestrator.run(request)
    assert response.status == "ok"
    text_blocks = [b for b in response.blocks if b.type.value == "text"]
    assert text_blocks
    body = text_blocks[0].text or ""
    assert "indexed course materials" in body.casefold()
