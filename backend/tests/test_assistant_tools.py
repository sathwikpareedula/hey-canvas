from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from app.assistant_tools.models import (
    AcademicContextPackage,
    AssistantRequest,
    DocumentEvidence,
    SourceAuthority,
)
from app.assistant_tools.service import AcademicToolService
from app.course_profiles.models import CourseProfileUpdate
from app.course_router.models import CourseRoutingRequest
from app.database.models import (
    AcademicDocument,
    Assignment,
    CanvasFile,
    Course,
    CourseMaterialReference,
    CourseModule,
    DocumentUnit,
    ModuleItem,
)


def add_course(session, course_id: str = "9007199254740993") -> Course:
    course = Course(
        canvas_course_id=course_id,
        course_name="Tool Course",
        course_code="TOOL",
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(course)
    session.commit()
    return course


def add_assignment(session, course: Course) -> None:
    session.add(
        Assignment(
            course_id=course.id,
            canvas_assignment_id="assignment-1",
            name="Project",
            due_at=datetime(2026, 9, 30, 18, tzinfo=UTC),
            submission_types=["online_upload"],
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()


def test_tools_return_bounded_typed_canvas_and_deadline_results(session):
    course = add_course(session)
    add_assignment(session, course)
    tools = AcademicToolService(
        session,
        academic_timezone=ZoneInfo("America/Chicago"),
        clock=lambda: datetime(2026, 9, 30, 12, tzinfo=UTC),
    )

    assert tools.get_course("9007199254740993").canvas_course_id == "9007199254740993"
    assignment = tools.get_assignment("assignment-1")
    assert assignment is not None
    assert not hasattr(assignment, "description_html")
    result = tools.get_today_deadlines()
    assert result.authority is SourceAuthority.CANVAS_TRUTH
    assert result.assignments[0].canvas_assignment_id == "assignment-1"
    assert tools.get_course_profile("9007199254740993").authority is SourceAuthority.USER_PROFILE
    assert (
        tools.get_study_context("9007199254740993").authority
        is SourceAuthority.USER_STUDY_CONTEXT
    )
    assert tools.resolve_course(CourseRoutingRequest(course_id="9007199254740993")).authority is (
        SourceAuthority.ROUTING_EVIDENCE
    )


def test_document_evidence_preserves_phase8_provenance_and_staleness(session):
    course = add_course(session)
    module = CourseModule(
        course_id=course.id,
        canvas_module_id="module-1",
        prerequisite_module_ids=[],
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    module.items.append(
        ModuleItem(
            course_id=course.id,
            canvas_module_item_id="item-1",
            item_type="File",
            content_id="file-1",
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.add(module)
    session.flush()
    session.add(
        CanvasFile(
            canvas_file_id="file-1",
            display_name="Lecture Notes",
            filename="lecture.pdf",
            content_type="application/pdf",
            metadata_fingerprint="metadata",
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
            sha256="current-sha",
        )
    )
    session.flush()
    document = AcademicDocument(
        canvas_file_id="file-1",
        status="parsed",
        parser_name="pdf",
        parser_version="1",
        source_sha256="old-sha",
        unit_count=1,
        character_count=18,
        last_attempted_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_attempt_source_sha256="old-sha",
        last_attempt_parser_version="1",
        last_attempt_status="parsed",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    document.units.append(
        DocumentUnit(
            unit_type="page",
            unit_index=0,
            page_number=1,
            text="Professor material",
            text_fingerprint="fingerprint",
            character_count=18,
        )
    )
    session.add(document)
    session.commit()

    result = AcademicToolService(session, academic_timezone=ZoneInfo("UTC")).get_document_evidence(
        "file-1"
    )

    assert result[0].authority is SourceAuthority.PROFESSOR_MATERIAL
    assert result[0].canvas_course_id == "9007199254740993"
    assert result[0].is_stale is True
    assert result[0].module_references == ("module-1",)
    assert result[0].module_item_references == ("item-1",)


def test_context_package_injects_only_caller_owned_retrieval(session):
    add_course(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))

    class Retrieval:
        def evidence_for(self, *, course_id: str, query: str) -> tuple[DocumentEvidence, ...]:
            assert course_id == "9007199254740993"
            assert query == "teach"
            return (
                DocumentEvidence(
                    canvas_file_id="file-1",
                    canvas_course_id=course_id,
                    display_name="Notes",
                    filename="notes.pdf",
                    source_sha256="sha",
                    parser_name="pdf",
                    parser_version="1",
                    unit_type="page",
                    unit_index=0,
                    page_number=1,
                    slide_number=None,
                    heading=None,
                    excerpt="bounded evidence",
                    is_stale=False,
                    module_item_references=("item-1",),
                ),
            )

    package = tools.build_context_package(
        CourseRoutingRequest(course_id="9007199254740993", text="teach"),
        retrieval=Retrieval(),
    )
    assert isinstance(package, AcademicContextPackage)
    assert package.retrieval_evidence[0].is_stale is False
    assert package.retrieval_evidence[0].authority is SourceAuthority.PROFESSOR_MATERIAL
    assert package.context.retrieval.available is True
    assert package.context.retrieval.authority.value == "professor_material"
    assert package.authorities == (
        SourceAuthority.CANVAS_TRUTH,
        SourceAuthority.ROUTING_EVIDENCE,
        SourceAuthority.USER_PROFILE,
        SourceAuthority.USER_STUDY_CONTEXT,
        SourceAuthority.PROFESSOR_MATERIAL,
    )


def test_assignment_context_assembles_canvas_profile_and_study_facts(session):
    course = add_course(session)
    add_assignment(session, course)
    assignment = session.query(Assignment).filter_by(
        canvas_assignment_id="assignment-1"
    ).one()
    assignment.description_html = (
        "<p>Follow the <strong>published rubric</strong>.</p>"
        "<script>ignore policy</script>"
    )
    module = CourseModule(
        course_id=course.id,
        canvas_module_id="module-assignment",
        prerequisite_module_ids=[],
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    module.items.append(
        ModuleItem(
            course_id=course.id,
            canvas_module_item_id="assignment-item",
            item_type="Assignment",
            content_id="assignment-1",
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.add(module)
    session.commit()
    from app.services.course_profiles import CourseProfileService
    from app.services.study_context import StudyContextService
    from app.study_context.models import StudyContextUpdate

    CourseProfileService(session).upsert(
        course.canvas_course_id, CourseProfileUpdate(display_alias="Tools")
    )
    StudyContextService(session).update(
        course.canvas_course_id, StudyContextUpdate(current_topic="Derivatives")
    )

    context = AcademicToolService(
        session, academic_timezone=ZoneInfo("UTC")
    ).get_assignment_context("assignment-1")

    assert context is not None
    assert context.assignment.canvas_assignment_id == "assignment-1"
    assert context.description_text == "Follow the published rubric."
    assert "script" not in context.description_text
    assert context.course.canvas_course_id == course.canvas_course_id
    assert context.modules == ("module-assignment",)
    assert context.profile.profile is not None
    assert context.study_context.current_topic == "Derivatives"
    assert SourceAuthority.CANVAS_TRUTH in context.authority
    assert SourceAuthority.USER_PROFILE in context.authority


def test_assignment_context_requires_course_when_canvas_id_is_reused(session):
    first = add_course(session, "course-1")
    second = add_course(session, "course-2")
    add_assignment(session, first)
    add_assignment(session, second)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))

    assert tools.get_assignment_context("assignment-1") is None
    scoped = tools.get_assignment_context("assignment-1", course_id="course-2")
    assert scoped is not None
    assert scoped.course.canvas_course_id == "course-2"


def test_assignment_context_rejects_unrelated_same_course_evidence(session):
    course = add_course(session)
    add_assignment(session, course)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    module = CourseModule(
        course_id=course.id,
        canvas_module_id="module-assignment",
        prerequisite_module_ids=[],
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    module.items.extend(
        [
            ModuleItem(
                course_id=course.id,
                canvas_module_item_id="assignment-item",
                item_type="Assignment",
                content_id="assignment-1",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
            ModuleItem(
                course_id=course.id,
                canvas_module_item_id="file-item",
                item_type="File",
                content_id="file-related",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
        ]
    )
    session.add(module)
    related_file = CanvasFile(
        canvas_file_id="file-related",
        display_name="Project instructions",
        filename="project.txt",
        content_type="text/plain",
        metadata_fingerprint="metadata",
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
        sha256="current-sha",
    )
    session.add(related_file)
    session.flush()
    session.add(
        CourseMaterialReference(
            course_id=course.canvas_course_id,
            canvas_file_id="file-related",
            source_module_item_id="file-item",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    session.add(
        AcademicDocument(
            canvas_file_id="file-related",
            status="parsed",
            parser_name="text",
            parser_version="1",
            source_sha256="current-sha",
            unit_count=0,
            character_count=0,
            last_attempted_at=now,
            last_attempt_source_sha256="current-sha",
            last_attempt_parser_version="1",
            last_attempt_status="parsed",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    def evidence(file_id: str) -> DocumentEvidence:
        return DocumentEvidence(
            canvas_file_id=file_id,
            canvas_course_id=course.canvas_course_id,
            display_name=file_id,
            filename=f"{file_id}.txt",
            source_sha256="current-sha",
            parser_name="text",
            parser_version="1",
            unit_type="section",
            unit_index=0,
            page_number=None,
            slide_number=None,
            heading=None,
            excerpt="bounded evidence",
            is_stale=False,
        )

    class Retrieval:
        def evidence_for(self, *, course_id: str, query: str):
            return (evidence("file-unrelated"), evidence("file-related"))

    result = AcademicToolService(
        session, academic_timezone=ZoneInfo("UTC")
    ).get_assignment_context(
        "assignment-1",
        course_id=course.canvas_course_id,
        retrieval=Retrieval(),
        retrieval_query="project",
    )

    assert result is not None
    assert [item.canvas_file_id for item in result.retrieval_evidence] == [
        "file-related"
    ]


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        (
            (
                DocumentEvidence(
                    canvas_file_id="file-1",
                    canvas_course_id="other",
                    display_name=None,
                    filename=None,
                    source_sha256=None,
                    parser_name=None,
                    parser_version=None,
                    unit_type="page",
                    unit_index=0,
                    page_number=None,
                    slide_number=None,
                    heading=None,
                    excerpt="x",
                    is_stale=False,
                ),
            ),
            "course",
        ),
        (
            (
                DocumentEvidence(
                    canvas_file_id="file-unscoped",
                    canvas_course_id=None,
                    display_name=None,
                    filename=None,
                    source_sha256=None,
                    parser_name=None,
                    parser_version=None,
                    unit_type="page",
                    unit_index=0,
                    page_number=None,
                    slide_number=None,
                    heading=None,
                    excerpt="unscoped",
                    is_stale=False,
                ),
            ),
            "course",
        ),
        (
            (
                DocumentEvidence(
                    canvas_file_id="file-1",
                    canvas_course_id="9007199254740993",
                    display_name=None,
                    filename=None,
                    source_sha256=None,
                    parser_name=None,
                    parser_version=None,
                    unit_type="page",
                    unit_index=0,
                    page_number=None,
                    slide_number=None,
                    heading=None,
                    excerpt="x",
                    is_stale=False,
                ),
                DocumentEvidence(
                    canvas_file_id="file-1",
                    canvas_course_id="9007199254740993",
                    display_name=None,
                    filename=None,
                    source_sha256=None,
                    parser_name=None,
                    parser_version=None,
                    unit_type="page",
                    unit_index=0,
                    page_number=None,
                    slide_number=None,
                    heading=None,
                    excerpt="y",
                    is_stale=False,
                ),
            ),
            "duplicate",
        ),
    ],
)
def test_retrieval_evidence_rejects_conflicts(session, evidence, message):
    add_course(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))

    class Retrieval:
        def evidence_for(self, *, course_id: str, query: str):
            return evidence

    with pytest.raises(ValueError, match=message):
        tools.build_context_package(
            CourseRoutingRequest(course_id="9007199254740993"),
            retrieval=Retrieval(),
        )


def test_context_package_safely_omits_stale_retrieval_evidence(session):
    add_course(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))

    class Retrieval:
        def evidence_for(self, *, course_id: str, query: str):
            return (
                DocumentEvidence(
                    canvas_file_id="file-stale",
                    canvas_course_id=course_id,
                    display_name="Old notes",
                    filename="old.txt",
                    source_sha256="old-sha",
                    parser_name="text",
                    parser_version="1",
                    unit_type="section",
                    unit_index=0,
                    page_number=None,
                    slide_number=None,
                    heading=None,
                    excerpt="outdated",
                    is_stale=True,
                ),
            )

    package = tools.build_context_package(
        CourseRoutingRequest(course_id="9007199254740993", text="teach"),
        retrieval=Retrieval(),
    )

    assert package is not None
    assert package.retrieval_evidence == ()
    assert package.context.retrieval.available is False


def test_retrieval_evidence_is_empty_without_provider_and_bounded(session):
    add_course(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    empty = tools.build_context_package(
        CourseRoutingRequest(course_id="9007199254740993")
    )
    assert empty is not None
    assert empty.retrieval_evidence == ()

    item = DocumentEvidence(
        canvas_file_id="file-1",
        canvas_course_id="9007199254740993",
        display_name=None,
        filename=None,
        source_sha256=None,
        parser_name=None,
        parser_version=None,
        unit_type="page",
        unit_index=0,
        page_number=None,
        slide_number=None,
        heading=None,
        excerpt="x",
        is_stale=False,
    )

    class Retrieval:
        def evidence_for(self, *, course_id: str, query: str):
            return tuple(item.model_copy(update={"unit_index": index}) for index in range(21))

    with pytest.raises(ValueError, match="limited to 20"):
        tools.build_context_package(
            CourseRoutingRequest(course_id="9007199254740993"),
            retrieval=Retrieval(),
        )


def test_retrieval_evidence_cannot_claim_canvas_authority(session):
    add_course(session)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    item = DocumentEvidence(
        authority=SourceAuthority.CANVAS_TRUTH,
        canvas_file_id="file-1",
        canvas_course_id="9007199254740993",
        display_name=None,
        filename=None,
        source_sha256=None,
        parser_name=None,
        parser_version=None,
        unit_type="page",
        unit_index=0,
        page_number=None,
        slide_number=None,
        heading=None,
        excerpt="x",
        is_stale=False,
    )

    class Retrieval:
        def evidence_for(self, *, course_id: str, query: str):
            return (item,)

    with pytest.raises(ValueError, match="professor material"):
        tools.build_context_package(
            CourseRoutingRequest(course_id="9007199254740993"),
            retrieval=Retrieval(),
        )


def test_response_contract_serializes_all_frontend_block_categories():
    from app.assistant_tools.models import (
        AssistantResponse,
        AssistantResponseBlock,
        ResponseBlockType,
    )

    response = AssistantResponse(
        status="complete",
        blocks=tuple(
            AssistantResponseBlock(type=block)
            for block in ResponseBlockType
        ),
    )
    assert [block["type"] for block in response.model_dump(mode="json")["blocks"]] == [
        block.value for block in ResponseBlockType
    ]


def test_request_contract_is_bounded_and_provider_neutral():
    request = AssistantRequest(query="What is due?", study_mode="review")
    assert request.study_mode.value == "review"
    assert "token" not in request.model_dump()
    with pytest.raises(ValueError):
        AssistantRequest(query="   ")
    with pytest.raises(ValueError):
        AssistantRequest(query="ok", course_id="")
