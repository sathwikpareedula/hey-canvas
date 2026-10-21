import hashlib
import io
from pathlib import Path

import pytest
from pypdf import PdfWriter
from app.database.document_repository import DocumentRepository
from app.database.file_repository import FileRepository
from app.documents.models import DocumentLimits
from app.retrieval.providers import (
    EmbeddingIdentity,
    SemanticMatch,
    SemanticProviderUnavailable,
)
from app.services.document_ingestion import DocumentIngestionService
from app.services.retrieval import RetrievalService
from app.services.retrieval_context import RetrievalContextPackager
from app.services.retrieval_tools import AcademicRetrievalTools
from sqlalchemy.orm import Session

from tests.test_document_ingestion import (
    seed_metadata,
    seed_references,
    store_local,
)

HUGE_FILE_ID = "92233720368547758081234567890"


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


async def seed_corpus(session: Session, root: Path, limits: DocumentLimits) -> None:
    course_one = [
        ("1001", HUGE_FILE_ID, "forward-kinematics.txt", b"forward kinematics robot frames"),
        ("1002", "7002", "quiz-syllabus.txt", b"quiz syllabus grading policy"),
        ("1003", "7004", "project.txt", b"project requirements and milestones"),
        ("1004", "7005", "unicode.txt", "café naïve résumé 学習".encode()),
    ]
    course_two = [
        ("2001", "7003", "neural.txt", b"neural network gradient descent"),
    ]
    seed_references(
        session,
        course_id="101",
        module_id="201",
        references=[(item, file_id, name) for item, file_id, name, _ in course_one],
    )
    seed_references(
        session,
        course_id="102",
        module_id="202",
        references=[(item, file_id, name) for item, file_id, name, _ in course_two],
    )
    for _, file_id, name, body in course_one + course_two:
        seed_metadata(session, file_id=file_id, filename=name, body_size=len(body))
        store_local(session, root, file_id, name, body)
    summary = await DocumentIngestionService(
        session=session, storage_root=root, limits=limits
    ).ingest_files([item[1] for item in course_one + course_two])
    assert summary.files_parsed == 5


class FakeSemanticProvider:
    provider_id = "local-test"
    model_version = "fixture-v1"

    def __init__(self, matches: list[SemanticMatch]) -> None:
        self.matches = matches
        self.calls: list[tuple[str, str | None, str | None, int]] = []

    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None,
        canvas_file_id: str | None,
        limit: int,
    ) -> list[SemanticMatch]:
        self.calls.append((query, canvas_course_id, canvas_file_id, limit))
        return self.matches[:limit]


class UnavailableSemanticProvider(FakeSemanticProvider):
    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None,
        canvas_file_id: str | None,
        limit: int,
    ) -> list[SemanticMatch]:
        raise SemanticProviderUnavailable("local model is not running")


def semantic_match(session: Session, file_id: str, *, score: float = 0.9) -> SemanticMatch:
    document = DocumentRepository(session).get(file_id)
    unit = DocumentRepository(session).units_for(file_id)[0]
    assert document is not None and document.source_sha256
    return SemanticMatch(
        canvas_file_id=file_id,
        unit_index=unit.unit_index,
        source_sha256=document.source_sha256,
        text_fingerprint=unit.text_fingerprint,
        score=score,
    )


@pytest.mark.asyncio
async def test_lexical_baseline_is_stable_filtered_provenance_first_and_opaque(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    service = RetrievalService(session)
    first = service.search("forward kinematics", canvas_course_id="101", limit=5)
    second = service.search("forward kinematics", canvas_course_id="101", limit=5)
    assert first == second
    assert first.semantic_status == "disabled"
    assert len(first.results) == 1
    hit = first.results[0]
    assert hit.evidence.canvas_file_id == HUGE_FILE_ID
    assert hit.evidence.canvas_course_id == "101"
    assert hit.evidence.source_sha256
    assert hit.evidence.parser_version
    assert hit.evidence.module_references[0].canvas_module_item_id == "1001"
    assert hit.evidence.authority == "professor_material"
    assert len(hit.snippet) <= 1000
    assert service.search("forward kinematics", canvas_course_id="102").results == ()
    assert service.search("forward kinematics", canvas_file_id="7002").results == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "file_id"),
    [
        ("quiz syllabus", "7002"),
        ("neural network gradient", "7003"),
        ("project requirements", "7004"),
        ("café naïve", "7005"),
    ],
)
async def test_realistic_and_unicode_queries(
    session: Session,
    tmp_path: Path,
    limits: DocumentLimits,
    query: str,
    file_id: str,
) -> None:
    await seed_corpus(session, tmp_path, limits)
    response = RetrievalService(session).search(query)
    assert response.results[0].evidence.canvas_file_id == file_id


@pytest.mark.asyncio
async def test_semantic_only_and_hybrid_fusion_are_verified_deduplicated_and_stable(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    provider = FakeSemanticProvider(
        [
            semantic_match(session, HUGE_FILE_ID),
            semantic_match(session, HUGE_FILE_ID, score=0.7),
            semantic_match(session, "7002", score=0.8),
        ]
    )
    service = RetrievalService(session, semantic_provider=provider)
    semantic = service.search("mechanism", mode="semantic", limit=5)
    hybrid = service.search("forward kinematics", mode="hybrid", limit=5)
    repeated = service.search("forward kinematics", mode="hybrid", limit=5)
    assert semantic.semantic_status == "available"
    assert [item.evidence.canvas_file_id for item in semantic.results] == [
        HUGE_FILE_ID,
        "7002",
    ]
    assert hybrid == repeated
    assert hybrid.results[0].evidence.canvas_file_id == HUGE_FILE_ID
    assert [signal.kind for signal in hybrid.results[0].signals] == ["lexical", "semantic"]
    assert len({item.evidence.citation_id for item in hybrid.results}) == len(hybrid.results)


@pytest.mark.asyncio
async def test_unavailable_provider_degrades_hybrid_but_not_semantic_only(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    service = RetrievalService(
        session, semantic_provider=UnavailableSemanticProvider([])
    )
    hybrid = service.search("forward kinematics", mode="hybrid")
    semantic = service.search("forward kinematics", mode="semantic")
    assert hybrid.semantic_status == "unavailable"
    assert len(hybrid.results) == 1
    assert semantic.semantic_status == "unavailable"
    assert semantic.results == ()


@pytest.mark.asyncio
async def test_unknown_stale_and_cross_course_semantic_matches_cannot_fabricate_evidence(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    stale = semantic_match(session, HUGE_FILE_ID).model_copy(
        update={"source_sha256": "f" * 64}
    )
    unknown = stale.model_copy(update={"canvas_file_id": "999999999999999999999"})
    cross_course = semantic_match(session, "7003")
    provider = FakeSemanticProvider([stale, unknown, cross_course])
    result = RetrievalService(session, semantic_provider=provider).search(
        "anything", mode="semantic", canvas_course_id="101"
    )
    assert result.semantic_status == "available"
    assert result.results == ()


@pytest.mark.asyncio
async def test_staleness_is_visible_without_discarding_last_good_units(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    record = FileRepository(session).get("7002")
    assert record is not None
    record.sha256 = "f" * 64
    session.commit()
    result = RetrievalService(session).search("quiz syllabus")
    assert result.results[0].evidence.is_stale is True


@pytest.mark.asyncio
async def test_context_package_is_bounded_and_empty_results_invent_nothing(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    response = RetrievalService(session).search("forward kinematics")
    package = RetrievalContextPackager().package(
        response, max_characters=12, max_items=1, max_excerpt_characters=100
    )
    empty = RetrievalContextPackager().package(
        RetrievalService(session).search("not-present-anywhere")
    )
    assert package.characters_used == 12
    assert package.truncated is True
    assert package.evidence[0].excerpt == response.results[0].snippet[:12]
    assert empty.no_evidence is True
    assert empty.evidence == ()


@pytest.mark.asyncio
async def test_unit_neighbors_and_source_detail_are_bounded_and_provenanced(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    seed_references(session, references=[("1001", "7001", "long.txt")])
    body = ("forward kinematics section. " * 20).encode()
    seed_metadata(session, file_id="7001", filename="long.txt", body_size=len(body))
    store_local(session, tmp_path, "7001", "long.txt", body)
    await DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits
    ).ingest_file("7001")
    tools = AcademicRetrievalTools(session)
    neighborhood = tools.retrieve_unit_context(
        "7001", 1, before=1, after=1, max_characters=250
    )
    source = tools.retrieve_source_detail("7001")
    assert neighborhood is not None
    assert [item.evidence.unit_index for item in neighborhood.units] == [0, 1, 2]
    assert sum(len(item.text) for item in neighborhood.units) <= 250
    assert source is not None
    assert source.document.canvas_file_id == "7001"
    assert source.citations[0].module_references[0].canvas_course_id == "101"
    assert "local_relative_path" not in source.model_dump_json()


def test_embedding_identity_tracks_complete_derived_lifecycle() -> None:
    identity = EmbeddingIdentity(
        canvas_file_id=HUGE_FILE_ID,
        unit_index=0,
        source_sha256=hashlib.sha256(b"source").hexdigest(),
        parser_version="1",
        text_fingerprint=hashlib.sha256(b"unit").hexdigest(),
        provider_id="local",
        model_version="v1",
    )
    assert identity.canvas_file_id == HUGE_FILE_ID
    assert identity.model_version == "v1"


@pytest.mark.asyncio
async def test_needs_ocr_filename_surfaces_index_limitation(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    scanned_id = "7999"
    scanned_name = "Braitenberg_scan.pdf"
    scanned_buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(scanned_buffer)
    scanned_body = scanned_buffer.getvalue()
    seed_references(
        session,
        course_id="101",
        module_id="201",
        references=[("9001", scanned_id, scanned_name)],
    )
    seed_metadata(
        session,
        file_id=scanned_id,
        filename=scanned_name,
        body_size=len(scanned_body),
        content_type="application/pdf",
    )
    store_local(session, tmp_path, scanned_id, scanned_name, scanned_body)
    summary = await DocumentIngestionService(
        session=session, storage_root=tmp_path, limits=limits
    ).ingest_files([scanned_id])
    assert summary.files_needing_ocr >= 1
    response = RetrievalService(session).search("braitenberg", canvas_course_id="101")
    assert response.results == ()
    assert response.index_limitation is not None
    assert "OCR required" in response.index_limitation
    assert "Braitenberg" in response.index_limitation


@pytest.mark.asyncio
async def test_query_and_result_bounds_and_malformed_queries(
    session: Session, tmp_path: Path, limits: DocumentLimits
) -> None:
    await seed_corpus(session, tmp_path, limits)
    service = RetrievalService(session)
    assert service.search("!!!").results == ()
    with pytest.raises(ValueError, match="at most 500"):
        service.search("x" * 501)
    with pytest.raises(ValueError, match="between 1 and 100"):
        service.search("query", limit=101)
    with pytest.raises(ValueError, match="file_id"):
        service.search("query", canvas_file_id="bad id")
