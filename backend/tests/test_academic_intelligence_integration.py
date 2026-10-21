from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.assistant_tools.models import SourceAuthority
from app.assistant_tools.service import AcademicToolService
from app.canvas.client import CanvasClient
from app.course_profiles.models import CourseProfileUpdate, TeachingDepth
from app.course_router.models import CourseRoutingRequest
from app.database.file_repository import FileRepository
from app.database.models import Assignment, Base, Course
from app.database.session import enable_sqlite_foreign_keys, get_session
from app.documents.models import DocumentLimits
from app.files.downloader import ControlledFileDownloader
from app.main import app
from app.retrieval.assistant_adapter import RetrievalEvidenceAdapter
from app.retrieval.providers import SemanticMatch, SemanticProviderUnavailable
from app.services.course_profiles import CourseProfileService
from app.services.study_context import StudyContextService
from app.study_context.models import StudyContextUpdate, StudyMode
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_retrieval import seed_corpus, semantic_match

HUGE_ID = "92233720368547758081234567890"


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


class FakeSemanticProvider:
    provider_id = "local-integration-test"
    model_version = "fixture-v1"

    def __init__(self, matches: list[SemanticMatch]) -> None:
        self._matches = matches

    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None,
        canvas_file_id: str | None,
        limit: int,
    ) -> list[SemanticMatch]:
        return self._matches[:limit]


class UnavailableSemanticProvider(FakeSemanticProvider):
    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None,
        canvas_file_id: str | None,
        limit: int,
    ) -> list[SemanticMatch]:
        raise SemanticProviderUnavailable("local provider unavailable")


@pytest.mark.asyncio
async def test_adapter_maps_lexical_evidence_with_complete_provenance(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)

    evidence = RetrievalEvidenceAdapter(session).evidence_for(
        course_id="101", query="forward kinematics"
    )

    assert len(evidence) == 1
    item = evidence[0]
    assert item.authority is SourceAuthority.PROFESSOR_MATERIAL
    assert item.canvas_course_id == "101"
    assert item.canvas_file_id == HUGE_ID
    assert item.parser_name == "uta-academic-document-parser"
    assert item.source_sha256 and item.parser_version
    assert item.module_references == ("201",)
    assert item.module_item_references == ("1001",)
    assert len(item.excerpt) <= 1000


@pytest.mark.asyncio
async def test_adapter_maps_hybrid_deduplicates_and_falls_back_when_semantic_unavailable(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    match = semantic_match(session, HUGE_ID)
    hybrid = RetrievalEvidenceAdapter(
        session,
        semantic_provider=FakeSemanticProvider([match, match]),
        mode="hybrid",
    ).evidence_for(course_id="101", query="forward kinematics")
    fallback = RetrievalEvidenceAdapter(
        session,
        semantic_provider=UnavailableSemanticProvider([]),
        mode="hybrid",
    ).evidence_for(course_id="101", query="forward kinematics")

    assert len(hybrid) == 1
    assert fallback == hybrid


@pytest.mark.asyncio
async def test_adapter_rejects_wrong_course_and_stale_evidence_and_preserves_opaque_ids(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    record = FileRepository(session).get("7005")
    assert record is not None
    record.sha256 = "f" * 64
    session.commit()

    evidence = RetrievalEvidenceAdapter(session).evidence_for(
        course_id="101", query="café naïve"
    )
    wrong_course = RetrievalEvidenceAdapter(session).evidence_for(
        course_id="102", query="café naïve"
    )
    huge = RetrievalEvidenceAdapter(session).evidence_for(
        course_id="101", query="forward kinematics"
    )

    assert evidence == ()
    assert wrong_course == ()
    assert huge[0].canvas_file_id == HUGE_ID


@pytest.mark.asyncio
async def test_academic_context_and_assignment_workflows_compose_retrieval(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    course = session.scalar(select(Course).where(Course.canvas_course_id == "101"))
    assert course is not None
    session.add(
        Assignment(
            course_id=course.id,
            canvas_assignment_id="assignment-robotics",
            name="Forward Kinematics Project",
            due_at=datetime(2026, 9, 30, 18, tzinfo=UTC),
            submission_types=["online_upload"],
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()
    CourseProfileService(session).upsert(
        "101", CourseProfileUpdate(teaching_depth=TeachingDepth.DETAILED)
    )
    StudyContextService(session).update(
        "101",
        StudyContextUpdate(
            current_topic="forward kinematics",
            study_mode=StudyMode.REVIEW,
        ),
    )
    adapter = RetrievalEvidenceAdapter(session)
    tools = AcademicToolService(
        session,
        academic_timezone=ZoneInfo("UTC"),
        clock=lambda: datetime(2026, 9, 30, 12, tzinfo=UTC),
    )

    package = tools.build_context_package(
        CourseRoutingRequest(course_id="101", text="forward kinematics"),
        retrieval=adapter,
    )
    assignment = tools.get_assignment_context(
        "assignment-robotics",
        retrieval=adapter,
        retrieval_query="forward kinematics",
    )

    assert package is not None and package.retrieval_evidence
    assert package.context.profile_preferences.teaching_depth is TeachingDepth.DETAILED
    assert package.context.study_context.current_topic == "forward kinematics"
    assert package.context.retrieval.available is True
    assert SourceAuthority.PROFESSOR_MATERIAL in package.authorities
    assert assignment is not None and assignment.retrieval_evidence
    assert assignment.retrieval_evidence[0].canvas_course_id == "101"
    assert SourceAuthority.PROFESSOR_MATERIAL in assignment.authority
    assert tools.get_today_deadlines(course_id="101").assignments[0].name == (
        "Forward Kinematics Project"
    )
    changes = tools.get_recent_changes(course_id="101").changes
    assert changes
    assert all(item.course_canvas_id == "101" for item in changes)


@pytest.mark.asyncio
async def test_no_evidence_and_ambiguous_routing_are_valid(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    adapter = RetrievalEvidenceAdapter(session)

    empty = tools.build_context_package(
        CourseRoutingRequest(course_id="101", text="not in any document"),
        retrieval=adapter,
    )
    explicit_course_with_wrong_document = tools.build_context_package(
        CourseRoutingRequest(course_id="102", document_id=HUGE_ID),
        retrieval=adapter,
    )

    assert empty is not None
    assert empty.retrieval_evidence == ()
    assert empty.context.retrieval.available is False
    assert explicit_course_with_wrong_document is not None
    assert explicit_course_with_wrong_document.context.course_id == "102"
    assert explicit_course_with_wrong_document.retrieval_evidence == ()
    assert explicit_course_with_wrong_document.context.retrieval.available is False


def override_factory(factory: sessionmaker[Session]) -> Callable[[], Iterator[Session]]:
    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    return override


@pytest.mark.asyncio
async def test_integrated_api_surface_is_local_only_and_safe(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    limits: DocumentLimits,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        await seed_corpus(session, tmp_path, limits)

    async def fail_network(*_: object, **__: object) -> object:
        raise AssertionError("academic context API must remain local-only")

    monkeypatch.setattr(CanvasClient, "get_json", fail_network)
    monkeypatch.setattr(CanvasClient, "get_paginated", fail_network)
    monkeypatch.setattr(ControlledFileDownloader, "download", fail_network)
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            read_paths = (
                "/health",
                "/api/courses",
                "/api/assignments",
                "/api/deadlines?window=next_7_days",
                "/api/modules",
                "/api/courses/101/modules",
                "/api/files",
                f"/api/files/{HUGE_ID}",
                "/api/changes",
                "/api/changes/summary",
                "/api/sync-runs",
                "/api/documents",
                f"/api/documents/{HUGE_ID}",
                f"/api/documents/{HUGE_ID}/units",
                "/api/document-search?q=forward%20kinematics&course_id=101",
                "/api/retrieval/search?q=forward%20kinematics&course_id=101",
                "/api/retrieval/context?q=forward%20kinematics&course_id=101",
                f"/api/retrieval/documents/{HUGE_ID}/units/0/context",
                f"/api/retrieval/documents/{HUGE_ID}/source",
                "/api/course-profiles",
                "/api/course-profiles/101",
                "/api/course-profiles/101/effective-context",
                "/api/study-context/101",
            )
            read_responses = [await client.get(path) for path in read_paths]
            router_response = await client.post(
                "/api/course-router/resolve", json={"course_id": "101"}
            )
            context_response = await client.post(
                "/api/academic-context/resolve", json={"course_id": "101"}
            )
            response = await client.post(
                "/api/academic-context/package?limit=5",
                json={"course_id": "101", "text": "forward kinematics"},
            )
    finally:
        app.dependency_overrides.clear()

    assert all(item.status_code == 200 for item in read_responses)
    assert router_response.status_code == context_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_evidence"][0]["authority"] == "professor_material"
    assert payload["context"]["retrieval"]["available"] is True
    encoded = response.text.casefold()
    for forbidden in (
        "local_relative_path",
        "authorization",
        "canvas_token",
        "x-amz-signature",
        "file://",
    ):
        assert forbidden not in encoded


def test_fresh_and_phase8_style_databases_register_integrated_tables(tmp_path: Path) -> None:
    fresh_engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    enable_sqlite_foreign_keys(fresh_engine)
    Base.metadata.create_all(fresh_engine)
    fresh_tables = set(inspect(fresh_engine).get_table_names())
    assert {"courses", "course_profiles", "study_contexts", "academic_documents"} <= fresh_tables
    fresh_engine.dispose()

    existing_engine = create_engine(f"sqlite:///{tmp_path / 'existing.db'}")
    enable_sqlite_foreign_keys(existing_engine)
    Course.__table__.create(existing_engine)
    with Session(existing_engine) as existing_session:
        existing_session.add(
            Course(
                canvas_course_id="opaque-course-id",
                course_name="Existing Course",
                first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
                last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
                last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        existing_session.commit()
    Base.metadata.create_all(existing_engine)
    with Session(existing_engine) as existing_session:
        preserved = existing_session.scalar(
            select(Course).where(Course.canvas_course_id == "opaque-course-id")
        )
        assert preserved is not None
    existing_tables = set(inspect(existing_engine).get_table_names())
    assert {"course_profiles", "study_contexts", "document_units"} <= existing_tables
    existing_engine.dispose()
