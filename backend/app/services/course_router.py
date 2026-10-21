"""Deterministic, local-only course resolution service."""

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.canvas.courses import _normalize_canvas_id
from app.course_router.models import (
    CourseRoutingRequest,
    CourseRoutingResult,
    ResolutionEvidence,
    ResolutionOutcome,
    ResolvedCourse,
)
from app.database.models import (
    Assignment,
    Course,
    CourseMaterialReference,
    CourseModule,
    ModuleItem,
)


class CourseRouterService:
    """Resolve known local courses without network, LLM, or fuzzy inference."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve(self, request: CourseRoutingRequest) -> CourseRoutingResult:
        direct = self._direct_candidates(request)
        if direct is not None:
            return direct
        if request.text is None or not request.text.strip():
            return CourseRoutingResult(
                outcome=ResolutionOutcome.UNRESOLVED,
                reason="no deterministic course signal was provided",
            )
        return self._resolve_text(request.text)

    def resolve_for_assignment(self, assignment_id: str) -> CourseRoutingResult:
        return self.resolve(CourseRoutingRequest(assignment_id=assignment_id))

    def resolve_for_document(self, document_id: str) -> CourseRoutingResult:
        return self.resolve(CourseRoutingRequest(document_id=document_id))

    def resolve_from_text(self, text: str) -> CourseRoutingResult:
        return self.resolve(CourseRoutingRequest(text=text))

    def _direct_candidates(self, request: CourseRoutingRequest) -> CourseRoutingResult | None:
        if request.course_id:
            normalized = _normalize_canvas_id(request.course_id, field_name="course id")
            if not self._course_ids_for_signal(
                normalized, ResolutionEvidence.EXPLICIT_COURSE
            ):
                return CourseRoutingResult(
                    outcome=ResolutionOutcome.UNRESOLVED,
                    reason="explicit course was not found locally",
                )
            return self._resolved(normalized, (ResolutionEvidence.EXPLICIT_COURSE,))

        signals: list[tuple[str, ResolutionEvidence, set[str]]] = []
        for value, evidence in (
            (request.assignment_id, ResolutionEvidence.ASSIGNMENT_MEMBERSHIP),
            (request.document_id, ResolutionEvidence.DOCUMENT_PROVENANCE),
            (request.module_id, ResolutionEvidence.MODULE_MEMBERSHIP),
            (request.module_item_id, ResolutionEvidence.MODULE_MEMBERSHIP),
            (request.active_course_id, ResolutionEvidence.ACTIVE_CONTEXT),
        ):
            if not value:
                continue
            normalized = _normalize_canvas_id(value, field_name="routing id")
            ids = self._course_ids_for_signal(normalized, evidence)
            if evidence is ResolutionEvidence.EXPLICIT_COURSE and not ids:
                return CourseRoutingResult(
                    outcome=ResolutionOutcome.UNRESOLVED,
                    reason="explicit course was not found locally",
                )
            if ids:
                signals.append((normalized, evidence, ids))
        if not signals:
            return None
        intersection = set.intersection(*(entry[2] for entry in signals))
        if len(intersection) == 1:
            evidence_items = tuple(entry[1] for entry in signals)
            return self._resolved(next(iter(intersection)), evidence_items)
        union = set.union(*(entry[2] for entry in signals))
        if len(union) > 1:
            return self._ambiguous(union, "strong routing signals conflict")
        return CourseRoutingResult(
            outcome=ResolutionOutcome.UNRESOLVED,
            reason="the supplied entity was not found locally",
        )

    def _course_ids_for_signal(self, value: str, evidence: ResolutionEvidence) -> set[str]:
        if evidence in {
            ResolutionEvidence.EXPLICIT_COURSE,
            ResolutionEvidence.ACTIVE_CONTEXT,
        }:
            return {
                value
            } if self._session.scalar(
                select(Course.canvas_course_id).where(Course.canvas_course_id == value)
            ) else set()
        if evidence is ResolutionEvidence.ASSIGNMENT_MEMBERSHIP:
            return set(
                self._session.scalars(
                    select(Course.canvas_course_id)
                    .join(Assignment, Assignment.course_id == Course.id)
                    .where(Assignment.canvas_assignment_id == value)
                )
            )
        if evidence is ResolutionEvidence.DOCUMENT_PROVENANCE:
            return {
                course_id
                for _, course_id in self._file_references(value)
            }
        if evidence is ResolutionEvidence.MODULE_MEMBERSHIP:
            return set(
                self._session.scalars(
                    select(Course.canvas_course_id)
                    .join(CourseModule, CourseModule.course_id == Course.id)
                    .outerjoin(ModuleItem, ModuleItem.module_id == CourseModule.id)
                    .where(
                        (CourseModule.canvas_module_id == value)
                        | (ModuleItem.canvas_module_item_id == value)
                    )
                )
            )
        return set()

    def _file_references(self, file_id: str) -> list[tuple[str, str]]:
        references = {
            (reference.canvas_file_id, reference.course_id)
            for reference in self._session.scalars(
                select(CourseMaterialReference).where(
                    CourseMaterialReference.canvas_file_id == file_id
                )
            )
        }
        references.update(
            self._session.execute(
                select(ModuleItem.content_id, Course.canvas_course_id)
                .join(Course, ModuleItem.course_id == Course.id)
                .where(ModuleItem.item_type == "File", ModuleItem.content_id == file_id)
            )
        )
        return sorted(references)

    def _resolve_text(self, text: str) -> CourseRoutingResult:
        normalized = _normalize_text(text)
        if not normalized:
            return CourseRoutingResult(
                outcome=ResolutionOutcome.UNRESOLVED,
                reason="text did not contain a usable course label",
            )
        exact_matches: dict[str, ResolutionEvidence] = {}
        scored_matches: dict[str, tuple[int, ResolutionEvidence]] = {}
        query_tokens = _meaningful_tokens(normalized)
        for course in self._session.scalars(
            select(Course).options(joinedload(Course.profile))
        ):
            if course.profile is not None and not course.profile.enabled:
                continue
            values = [
                (course.course_name, ResolutionEvidence.COURSE_NAME_MATCH),
                (course.course_code, ResolutionEvidence.COURSE_NAME_MATCH),
            ]
            if course.profile and course.profile.enabled:
                values.extend(
                    [
                        (course.profile.display_alias, ResolutionEvidence.PROFILE_ALIAS),
                        (course.profile.short_label, ResolutionEvidence.PROFILE_SHORT_LABEL),
                    ]
                )
            for candidate, evidence in values:
                if not candidate:
                    continue
                candidate_text = _normalize_text(candidate)
                if candidate_text == normalized:
                    exact_matches[course.canvas_course_id] = evidence
                    continue
                candidate_tokens = _meaningful_tokens(candidate_text)
                matched = sum(
                    any(
                        _token_matches(query_token, course_token)
                        for course_token in candidate_tokens
                    )
                    for query_token in query_tokens
                )
                required = max(1, (len(query_tokens) + 1) // 2)
                if query_tokens and matched >= required:
                    scored_matches[course.canvas_course_id] = (matched, evidence)
        matches = exact_matches or {
            course_id: evidence
            for course_id, (score, evidence) in scored_matches.items()
            if score == max((item[0] for item in scored_matches.values()), default=0)
        }
        if len(matches) == 1:
            course_id, evidence = next(iter(matches.items()))
            return self._resolved(course_id, (evidence,))
        if len(matches) > 1:
            return self._ambiguous(set(matches), "course text matches multiple courses")
        return CourseRoutingResult(
            outcome=ResolutionOutcome.UNRESOLVED,
            reason="no exact profile alias, label, or course name match",
        )

    def _resolved(
        self, course_id: str, evidence: tuple[ResolutionEvidence, ...]
    ) -> CourseRoutingResult:
        course = self._session.scalar(
            select(Course).where(Course.canvas_course_id == course_id)
        )
        if course is None:
            return CourseRoutingResult(
                outcome=ResolutionOutcome.UNRESOLVED,
                reason="course is no longer available locally",
            )
        return CourseRoutingResult(
            outcome=ResolutionOutcome.RESOLVED,
            course=ResolvedCourse(
                course_id=course.canvas_course_id,
                course_name=course.course_name,
                course_code=course.course_code,
            ),
            evidence=evidence,
            reason="course resolved from deterministic local evidence",
        )

    def _ambiguous(self, course_ids: set[str], reason: str) -> CourseRoutingResult:
        courses = self._session.scalars(
            select(Course).where(Course.canvas_course_id.in_(course_ids))
        )
        candidates = tuple(
            ResolvedCourse(
                course_id=course.canvas_course_id,
                course_name=course.course_name,
                course_code=course.course_code,
            )
            for course in sorted(courses, key=lambda item: item.canvas_course_id)
        )
        return CourseRoutingResult(
            outcome=ResolutionOutcome.AMBIGUOUS,
            candidates=candidates,
            reason=reason,
        )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w\s-]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


_ROUTING_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "class", "course", "exam", "explain", "for", "help",
        "in", "make", "me", "my", "next", "of", "on", "prepared", "quiz", "should",
        "study", "the", "to", "upcoming", "what",
    }
)


def _meaningful_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in value.replace("-", " ").split()
        if len(token) >= 3 and token not in _ROUTING_STOP_WORDS
    )


def _token_matches(left: str, right: str) -> bool:
    if left == right:
        return True
    return min(len(left), len(right)) >= 5 and (
        left.startswith(right) or right.startswith(left)
    )
