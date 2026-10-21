"""Deterministic local academic tools for future assistant orchestration."""

from collections.abc import Callable
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.academic_context.models import (
    AcademicContext,
    ContextAuthority,
    RetrievalEvidenceSlot,
)
from app.assistant_tools.models import (
    AcademicContextPackage,
    AssignmentContext,
    AssignmentToolRecord,
    ChangeToolResult,
    CourseProfileToolResult,
    CourseToolRecord,
    DeadlineToolResult,
    DocumentEvidence,
    DocumentSearchToolResult,
    DocumentToolResult,
    DocumentUnitToolResult,
    RetrievalEvidenceProvider,
    RoutingToolResult,
    SourceAuthority,
    StudyContextToolResult,
)
from app.course_router.models import CourseRoutingRequest
from app.database.assignment_repository import AssignmentRepository
from app.database.models import Assignment, Course, CourseModule
from app.documents.models import DocumentView
from app.services.academic_context import AcademicContextService
from app.services.change_query import ChangeQueryService
from app.services.course_profiles import CourseProfileService
from app.services.course_router import CourseRouterService
from app.services.deadlines import DeadlineService, DeadlineWindow
from app.services.document_query import DocumentQueryService
from app.services.document_search import DocumentSearchService
from app.services.study_context import StudyContextService


class AcademicToolService:
    """Facade that returns typed projections and never performs network writes."""

    def __init__(
        self,
        session: Session,
        *,
        academic_timezone: ZoneInfo,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._timezone = academic_timezone
        self._clock = clock

    def get_courses(self, *, limit: int = 100) -> tuple[CourseToolRecord, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        courses = self._session.scalars(
            select(Course).order_by(Course.course_name, Course.canvas_course_id).limit(limit)
        )
        return tuple(self._course(item) for item in courses)

    def get_course(self, course_id: str) -> CourseToolRecord | None:
        course = self._session.scalar(
            select(Course).where(Course.canvas_course_id == course_id)
        )
        return self._course(course) if course else None

    def get_assignments(
        self, *, course_id: str | None = None, limit: int = 100
    ) -> tuple[AssignmentToolRecord, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return tuple(
            self._assignment(item)
            for item in AssignmentRepository(self._session).list_all(
                canvas_course_id=course_id
            )[:limit]
        )

    def get_assignment(
        self, assignment_id: str, *, course_id: str | None = None
    ) -> AssignmentToolRecord | None:
        statement = (
            select(Assignment)
            .join(Course)
            .where(Assignment.canvas_assignment_id == assignment_id)
        )
        if course_id is not None:
            statement = statement.where(Course.canvas_course_id == course_id)
        assignment = self._session.scalar(statement)
        return self._assignment(assignment) if assignment else None

    def assignment_record(self, assignment: Assignment) -> AssignmentToolRecord:
        return self._assignment(assignment)

    def assignment_entity(
        self, assignment_id: str, *, course_id: str | None = None
    ) -> Assignment | None:
        statement = (
            select(Assignment)
            .join(Course)
            .where(Assignment.canvas_assignment_id == assignment_id)
        )
        if course_id is not None:
            statement = statement.where(Course.canvas_course_id == course_id)
        return self._session.scalar(statement)

    @property
    def session(self) -> Session:
        return self._session

    @property
    def academic_timezone(self) -> ZoneInfo:
        return self._timezone

    def get_deadlines(
        self, window: DeadlineWindow, *, course_id: str | None = None
    ) -> DeadlineToolResult:
        service = DeadlineService(
            AssignmentRepository(self._session),
            academic_timezone=self._timezone,
            clock=self._clock,
        )
        assignments = service.query(window, canvas_course_id=course_id)
        norm_window = service.normalized_window(window)
        return DeadlineToolResult(
            window=window.value,
            normalized_window=norm_window,
            assignments=tuple(self._assignment(item) for item in assignments),
        )


    def get_today_deadlines(self, *, course_id: str | None = None) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.TODAY, course_id=course_id)

    def get_tomorrow_deadlines(self, *, course_id: str | None = None) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.TOMORROW, course_id=course_id)

    def get_this_week_deadlines(self, *, course_id: str | None = None) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.THIS_WEEK, course_id=course_id)

    def get_next_week_deadlines(self, *, course_id: str | None = None) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.NEXT_WEEK, course_id=course_id)

    def get_upcoming_deadlines(self, *, course_id: str | None = None) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.UPCOMING, course_id=course_id)

    def get_next_7_days_deadlines(
        self, *, course_id: str | None = None
    ) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.NEXT_7_DAYS, course_id=course_id)

    def get_overdue_deadlines(self, *, course_id: str | None = None) -> DeadlineToolResult:
        return self.get_deadlines(DeadlineWindow.OVERDUE, course_id=course_id)

    def get_calendar_month_deadlines(
        self, year: int, month: int, *, course_id: str | None = None
    ) -> DeadlineToolResult:
        assignments = DeadlineService(
            AssignmentRepository(self._session),
            academic_timezone=self._timezone,
            clock=self._clock,
        ).query_month(year, month, canvas_course_id=course_id)
        return DeadlineToolResult(
            window=f"{year:04d}-{month:02d}",
            assignments=tuple(self._assignment(item) for item in assignments),
        )

    def get_recent_changes(
        self, *, course_id: str | None = None, since: datetime | None = None, limit: int = 100
    ) -> ChangeToolResult:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return ChangeToolResult(
            changes=tuple(
                ChangeQueryService(self._session).list_changes(
                    course_id=course_id, since=since, limit=limit
                )
            )
        )

    def get_documents(
        self, *, course_id: str | None = None, limit: int = 100
    ) -> DocumentToolResult:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return DocumentToolResult(
            documents=tuple(
                DocumentQueryService(self._session).list_documents(
                    canvas_course_id=course_id, limit=limit
                )
            )
        )

    def get_document_units(
        self, file_id: str, *, limit: int = 200
    ) -> DocumentUnitToolResult:
        if not 1 <= limit <= 2000:
            raise ValueError("limit must be between 1 and 2000")
        units = DocumentQueryService(self._session).units(file_id, limit=limit)
        return DocumentUnitToolResult(units=tuple(units or ()))

    def get_document_evidence(
        self,
        file_id: str,
        *,
        course_id: str | None = None,
        limit: int = 20,
        excerpt_limit: int = 1000,
    ) -> tuple[DocumentEvidence, ...]:
        if not 1 <= limit <= 100 or not 1 <= excerpt_limit <= 1000:
            raise ValueError("evidence limits are out of bounds")
        documents = DocumentQueryService(self._session).list_documents(
            canvas_file_id=file_id, limit=1
        )
        if not documents:
            return ()
        document = documents[0]
        units = self.get_document_units(file_id, limit=limit).units
        evidence: list[DocumentEvidence] = []
        for unit in units:
            references = tuple(
                reference
                for reference in unit.references
                if course_id is None or reference.canvas_course_id == course_id
            )
            if course_id is not None and not references:
                continue
            evidence.append(
                DocumentEvidence(
                canvas_file_id=unit.canvas_file_id,
                canvas_course_id=(
                    references[0].canvas_course_id if references else None
                ),
                display_name=document.display_name,
                filename=document.filename,
                source_sha256=unit.source_sha256,
                parser_name=unit.parser_name,
                parser_version=unit.parser_version,
                unit_type=unit.unit_type,
                unit_index=unit.unit_index,
                page_number=unit.page_number,
                slide_number=unit.slide_number,
                heading=unit.heading,
                excerpt=unit.text[:excerpt_limit],
                is_stale=document.is_stale,
                module_references=tuple(
                    reference.canvas_module_id for reference in references
                ),
                module_item_references=tuple(
                    reference.canvas_module_item_id for reference in references
                ),
                )
            )
        return tuple(evidence)

    def search_documents(
        self, query: str, *, course_id: str | None = None, limit: int = 20
    ) -> DocumentSearchToolResult:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return DocumentSearchToolResult(
            hits=tuple(
                DocumentSearchService(self._session).search(
                    query, canvas_course_id=course_id, limit=limit
                )
            )
        )

    def resolve_course(self, request: CourseRoutingRequest) -> RoutingToolResult:
        return RoutingToolResult(
            result=CourseRouterService(self._session).resolve(request)
        )

    def get_course_profile(self, course_id: str) -> CourseProfileToolResult:
        return CourseProfileToolResult(profile=CourseProfileService(self._session).get(course_id))

    def get_study_context(self, course_id: str) -> StudyContextToolResult:
        return StudyContextToolResult(context=StudyContextService(self._session).get(course_id))

    def build_context_package(
        self,
        request: CourseRoutingRequest,
        *,
        retrieval: RetrievalEvidenceProvider | None = None,
    ) -> AcademicContextPackage | None:
        context = AcademicContextService(self._session).build(request)
        if context is None:
            return None
        if request.document_id is not None:
            evidence = self.get_document_evidence(
                request.document_id,
                course_id=context.course_id,
                limit=20,
            )
        elif retrieval is not None:
            evidence = tuple(
                item
                for item in retrieval.evidence_for(
                    course_id=context.course_id,
                    query=request.text or "",
                )
                if not item.is_stale
            )
        else:
            evidence = ()
        evidence = tuple(item for item in evidence if not item.is_stale)
        validated = self._validate_retrieval_evidence(
            context.course_id, tuple(evidence)
        )
        authorities: tuple[SourceAuthority, ...] = (
            (
                SourceAuthority.CANVAS_TRUTH,
                SourceAuthority.ROUTING_EVIDENCE,
                SourceAuthority.USER_PROFILE,
                SourceAuthority.USER_STUDY_CONTEXT,
                SourceAuthority.PROFESSOR_MATERIAL,
            )
            if validated
            else (
                SourceAuthority.CANVAS_TRUTH,
                SourceAuthority.ROUTING_EVIDENCE,
                SourceAuthority.USER_PROFILE,
                SourceAuthority.USER_STUDY_CONTEXT,
            )
        )
        if validated:
            context = context.model_copy(
                update={
                    "retrieval": RetrievalEvidenceSlot(
                        available=True,
                        authority=ContextAuthority.PROFESSOR_MATERIAL,
                    )
                }
            )
        return AcademicContextPackage(
            context=context,
            retrieval_evidence=validated,
            authorities=authorities,
        )

    def build_academic_context(
        self,
        request: CourseRoutingRequest,
    ) -> AcademicContext | None:
        return AcademicContextService(self._session).build(request)

    def get_assignment_context(
        self,
        assignment_id: str,
        *,
        course_id: str | None = None,
        retrieval: RetrievalEvidenceProvider | None = None,
        retrieval_query: str | None = None,
        allow_semantic_retrieval: bool = True,
    ) -> AssignmentContext | None:
        statement = (
            select(Assignment)
            .join(Course)
            .where(Assignment.canvas_assignment_id == assignment_id)
        )
        if course_id is not None:
            statement = statement.where(Course.canvas_course_id == course_id)
        assignments = list(self._session.scalars(statement.limit(2)))
        if len(assignments) != 1:
            return None
        assignment = assignments[0]
        course = assignment.course
        module_ids = tuple(
            module.canvas_module_id
            for module in self._session.scalars(
                select(CourseModule)
                .options(selectinload(CourseModule.items))
                .where(CourseModule.course_id == course.id)
            )
            if any(
                item.item_type == "Assignment"
                and item.content_id == assignment_id
                for item in module.items
            )
        )
        documents = tuple(
            document
            for document in self.get_documents(course_id=course.canvas_course_id).documents
            if any(
                reference.canvas_module_id in module_ids
                for reference in document.references
            )
        )
        from app.services.cross_source_linking import (
            build_canvas_text_evidence,
            extract_topics_from_text,
            link_topics_to_module_items,
        )

        evidence: tuple[DocumentEvidence, ...] = ()
        query = retrieval_query or assignment.name or ""
        canvas_text_evidence = build_canvas_text_evidence(
            self._session,
            canvas_course_id=course.canvas_course_id,
            query=query,
            assignment_name=assignment.name,
        )
        safe_description = _assignment_description_text(assignment.description_html) or ""
        topics = extract_topics_from_text(
            *(item.excerpt for item in canvas_text_evidence),
            safe_description,
        )
        topic_module_links = link_topics_to_module_items(
            self._session,
            canvas_course_id=course.canvas_course_id,
            topics=topics,
            allowed_module_ids=module_ids,
        )
        if topics and not topic_module_links:
            topic_module_links = link_topics_to_module_items(
                self._session,
                canvas_course_id=course.canvas_course_id,
                topics=topics,
            )
        if documents:
            evidence = self._documents_to_evidence(
                course.canvas_course_id,
                documents,
            )
        if retrieval is not None and allow_semantic_retrieval:
            topic_query = " ".join(topics[:4]) if topics else query
            raw_evidence = [
                item
                for item in retrieval.evidence_for(
                    course_id=course.canvas_course_id,
                    query=topic_query,
                )
                if not item.is_stale
            ]
            candidate_evidence = self._validate_retrieval_evidence(
                course.canvas_course_id,
                tuple(raw_evidence[:8]),
            )
            if documents:
                related_file_ids = {document.canvas_file_id for document in documents}
                candidate_evidence = tuple(
                    item
                    for item in candidate_evidence
                    if item.canvas_file_id in related_file_ids
                )
            if candidate_evidence:
                evidence = AcademicToolService._merge_document_evidence(
                    evidence,
                    candidate_evidence,
                    limit=8,
                )
        authorities: tuple[SourceAuthority, ...] = (
            SourceAuthority.CANVAS_TRUTH,
            SourceAuthority.USER_PROFILE,
            SourceAuthority.USER_STUDY_CONTEXT,
        )
        if documents or evidence:
            authorities += (SourceAuthority.PROFESSOR_MATERIAL,)
        if canvas_text_evidence:
            authorities = tuple(
                dict.fromkeys((*authorities, SourceAuthority.CANVAS_TRUTH))
            )
        return AssignmentContext(
            assignment=self._assignment(assignment),
            description_text=_assignment_description_text(assignment.description_html),
            course=self._course(course),
            modules=module_ids,
            related_documents=documents,
            profile=CourseProfileService(self._session).get(course.canvas_course_id),
            study_context=StudyContextService(self._session).get(course.canvas_course_id),
            retrieval_evidence=evidence,
            canvas_text_evidence=canvas_text_evidence,
            topic_module_links=topic_module_links,
            authority=authorities,
        )

    def _documents_to_evidence(
        self,
        canvas_course_id: str,
        documents: tuple[DocumentView, ...],
    ) -> tuple[DocumentEvidence, ...]:
        merged: list[DocumentEvidence] = []
        for document in documents[:8]:
            # A prior parse remains available for local inspection and rollback,
            # but it is not current professor evidence after Canvas metadata changes.
            if getattr(document, "is_stale", False) or document.is_stale:
                continue
            file_id = document.canvas_file_id
            if not file_id:
                continue
            for item in self.get_document_evidence(
                file_id,
                course_id=canvas_course_id,
                limit=1,
                excerpt_limit=400,
            ):
                if not item.is_stale:
                    merged.append(item)
        return self._validate_retrieval_evidence(canvas_course_id, tuple(merged)[:8])

    @staticmethod
    def _merge_document_evidence(
        primary: tuple[DocumentEvidence, ...],
        extra: tuple[DocumentEvidence, ...],
        *,
        limit: int = 20,
    ) -> tuple[DocumentEvidence, ...]:
        seen: set[str] = set()
        merged: list[DocumentEvidence] = []
        for item in (*primary, *extra):
            key = f"{item.canvas_file_id}:{item.unit_index}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                break
        return tuple(merged)

    @staticmethod
    def _validate_retrieval_evidence(
        course_id: str, evidence: tuple[DocumentEvidence, ...]
    ) -> tuple[DocumentEvidence, ...]:
        if len(evidence) > 20:
            raise ValueError("retrieval evidence is limited to 20 items")
        seen: set[tuple[str, int]] = set()
        current: list[DocumentEvidence] = []
        for item in evidence:
            if item.authority is not SourceAuthority.PROFESSOR_MATERIAL:
                raise ValueError("retrieval evidence must be professor material")
            if item.canvas_course_id != course_id:
                raise ValueError("retrieval evidence course does not match context")
            if item.is_stale:
                continue
            key = (item.canvas_file_id, item.unit_index)
            if key in seen:
                raise ValueError("retrieval evidence contains duplicate units")
            seen.add(key)
            current.append(item)
        return tuple(current)

    @staticmethod
    def _course(course: Course) -> CourseToolRecord:
        return CourseToolRecord(
            canvas_course_id=course.canvas_course_id,
            course_code=course.course_code,
            course_name=course.course_name,
            term_name=course.term_name,
            workflow_state=course.workflow_state,
            enrollment_state=course.enrollment_state,
        )

    @staticmethod
    def _assignment(assignment: Assignment) -> AssignmentToolRecord:
        return AssignmentToolRecord(
            canvas_assignment_id=assignment.canvas_assignment_id,
            canvas_course_id=assignment.canvas_course_id,
            name=assignment.name,
            due_at=assignment.due_at,
            unlock_at=assignment.unlock_at,
            lock_at=assignment.lock_at,
            points_possible=assignment.points_possible,
            submission_types=tuple(assignment.submission_types),
            workflow_state=assignment.workflow_state,
            published=assignment.published,
        )


class LocalDocumentRetrievalProvider:
    """Default local retrieval adapter over already indexed authorized documents."""

    def __init__(self, tools: AcademicToolService) -> None:
        self._tools = tools

    def evidence_for(self, *, course_id: str, query: str) -> tuple[DocumentEvidence, ...]:
        hits = self._tools.search_documents(query, course_id=course_id, limit=20).hits
        return tuple(
            DocumentEvidence(
                canvas_file_id=hit.canvas_file_id,
                canvas_course_id=(
                    hit.references[0].canvas_course_id if hit.references else course_id
                ),
                display_name=hit.display_name,
                filename=hit.filename,
                source_sha256=hit.source_sha256,
                parser_name=None,
                parser_version=None,
                unit_type=hit.unit_type,
                unit_index=hit.unit_index,
                page_number=hit.page_number,
                slide_number=hit.slide_number,
                heading=hit.heading,
                excerpt=hit.snippet[:1000],
                is_stale=hit.is_stale,
                module_references=tuple(
                    reference.canvas_module_id for reference in hit.references
                ),
                module_item_references=tuple(
                    reference.canvas_module_item_id for reference in hit.references
                ),
            )
            for hit in hits
            if not hit.is_stale
        )


class _CanvasHTMLTextExtractor(HTMLParser):
    """Extract bounded visible text without retaining markup or executable content."""

    _IGNORED_ELEMENTS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag.casefold() in self._IGNORED_ELEMENTS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self._IGNORED_ELEMENTS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _assignment_description_text(value: str | None) -> str | None:
    if not value:
        return None
    parser = _CanvasHTMLTextExtractor()
    try:
        parser.feed(value[:100_000])
        parser.close()
    except Exception:
        return None
    normalized = "".join(parser.parts)
    # Canvas content can contain double-escaped numeric entities (for example
    # ``&amp;#x20;``). Decode one additional bounded layer after HTML parsing so
    # student-visible text is readable without reinterpreting it as markup.
    normalized = unescape(normalized)
    normalized = " ".join(normalized.split())
    return normalized[:4000] or None
