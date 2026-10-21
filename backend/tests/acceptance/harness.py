"""World builder, ask helpers and fixture-truth oracles for the acceptance campaign."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.assistant_orchestration.models import (
    AcademicModelProvider,
    AssistantEvent,
    AssistantEventType,
    AssistantModelInput,
)
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import (
    AssistantRequest,
    AssistantResponse,
    AssistantResponseBlock,
    ResponseBlockType,
)
from app.assistant_tools.service import AcademicToolService, LocalDocumentRetrievalProvider
from app.database.models import Base
from app.database.session import enable_sqlite_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from tests.acceptance.student_factory import (
    AssignmentTruth,
    CourseTruth,
    FileTruth,
    StudentProfile,
    seed_student,
)


class CapturingProvider(AcademicModelProvider):
    """Records what the orchestrator hands the model and answers only from it."""

    def __init__(self) -> None:
        self.inputs: list[AssistantModelInput] = []

    def complete(self, model_input: AssistantModelInput) -> AssistantResponse:
        self.inputs.append(model_input)
        if model_input.evidence:
            top = model_input.evidence[0]
            label = top.display_name or top.filename or "course material"
            text = f"From {label}: {top.excerpt}"
        else:
            text = "I do not have course material to answer from."
        return AssistantResponse(
            status="ok",
            blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
            course_id=model_input.plan.course_id,
        )

    def stream(self, model_input: AssistantModelInput) -> tuple[AssistantEvent, ...]:
        response = self.complete(model_input)
        return (
            AssistantEvent(type=AssistantEventType.STARTED),
            AssistantEvent(type=AssistantEventType.COMPLETED, response=response),
        )


class RaisingProvider(AcademicModelProvider):
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls = 0

    def complete(self, model_input: AssistantModelInput) -> AssistantResponse:
        self.calls += 1
        raise self._exc

    def stream(self, model_input: AssistantModelInput) -> tuple[AssistantEvent, ...]:
        self.calls += 1
        raise self._exc


@dataclass
class World:
    profile: StudentProfile
    session: Session
    provider: AcademicModelProvider = field(default_factory=SyntheticAcademicModelProvider)

    def tools(self) -> AcademicToolService:
        return AcademicToolService(
            self.session,
            academic_timezone=self.profile.tz,
            clock=lambda: self.profile.now,
        )

    def orchestrator(
        self, provider: AcademicModelProvider | None = None
    ) -> AcademicAssistantOrchestrator:
        tools = self.tools()
        return AcademicAssistantOrchestrator(
            tools,
            provider or self.provider,
            retrieval=LocalDocumentRetrievalProvider(tools),
        )

    def request(self, query: str, **kwargs: Any) -> AssistantRequest:
        return AssistantRequest(query=query, operation="answer", **kwargs)

    def ask(
        self,
        query: str,
        *,
        provider: AcademicModelProvider | None = None,
        **kwargs: Any,
    ) -> AssistantResponse:
        return self.orchestrator(provider).run(self.request(query, **kwargs))

    def stream_final(
        self,
        query: str,
        *,
        provider: AcademicModelProvider | None = None,
        **kwargs: Any,
    ) -> tuple[list[AssistantEvent], AssistantResponse | None]:
        events = list(self.orchestrator(provider).events(self.request(query, **kwargs)))
        completed = [e for e in events if e.type is AssistantEventType.COMPLETED]
        return events, (completed[-1].response if completed else None)


@contextmanager
def student_world(profile: StudentProfile) -> Iterator[World]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            seed_student(session, profile)
            yield World(profile=profile, session=session)
    finally:
        engine.dispose()


def response_text(response: AssistantResponse) -> str:
    return "\n".join(block.text or "" for block in response.blocks if block.text)


# ---------------------------------------------------------------------------
# Fixture-truth oracles (independent of production formatting helpers)
# ---------------------------------------------------------------------------


def fmt_due(due: datetime, profile: StudentProfile) -> str:
    local = due.astimezone(profile.tz)
    hour12 = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return (
        f"{local:%B} {local.day}, {local.year} at {hour12}:{local.minute:02d} "
        f"{meridiem} {local.tzname()}"
    )


def due_on(profile: StudentProfile, offset_days: int) -> list[tuple[CourseTruth, AssignmentTruth]]:
    from datetime import timedelta

    target = profile.local_today() + timedelta(days=offset_days)
    found = []
    for course in profile.courses:
        for assignment in course.assignments:
            if assignment.due_at and assignment.due_at.astimezone(profile.tz).date() == target:
                found.append((course, assignment))
    return found


def course_by_id(profile: StudentProfile, course_id: str) -> CourseTruth:
    return next(c for c in profile.courses if c.canvas_id == course_id)


def linked_files(course: CourseTruth, assignment: AssignmentTruth) -> list[FileTruth]:
    return [f for f in course.files if f.in_module_of == assignment.canvas_id]


def unlinked_files(course: CourseTruth, assignment: AssignmentTruth) -> list[FileTruth]:
    return [f for f in course.files if f.in_module_of != assignment.canvas_id]


def other_course_files(profile: StudentProfile, course: CourseTruth) -> list[FileTruth]:
    return [f for c in profile.courses if c is not course for f in c.files]


# ---------------------------------------------------------------------------
# Universal product-quality invariants
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b"  # noqa: E501
)
_TIME_ZONE_RE = re.compile(r"at \d{1,2}:\d{2} [AP]M(?: ([A-Za-z]{2,5}))?")
_LEAK_RE = re.compile(
    r"(/home/|/tmp/|[A-Z]:\\|Traceback|sqlalchemy|sqlite|\.db\b|"
    r"OperationalError|RuntimeError|ValueError|provider unavailable|Authorization|"
    r"Bearer"
    r"\s|api[_-]?key|secret)",
    re.IGNORECASE,
)
_COVERAGE_CLAIM_RE = re.compile(
    r"(this (?:quiz|exam|assignment) (?:covers|will cover)|covered topics (?:are|include)|"
    r"you will be tested on)",
    re.IGNORECASE,
)


def invariant_violations(
    profile: StudentProfile,
    response: AssistantResponse,
    *,
    course: CourseTruth | None = None,
    allow_injection_quote: bool = False,
    check_dates: bool = True,
) -> list[str]:
    """Return every violated release invariant for one assistant response."""

    problems: list[str] = []
    text = response_text(response)
    if response.status != "ok":
        problems.append(f"status={response.status}")
    if not text.strip() or text.strip() == "None":
        problems.append("empty visible text")

    known_dates = {
        fmt_due(a.due_at, profile).split(" at ")[0]
        for c in profile.courses
        for a in c.assignments
        if a.due_at
    }
    for match in _DATE_RE.findall(text):
        if check_dates and match not in known_dates and not allow_injection_quote:
            problems.append(f"invented date {match!r}")

    allowed_zone = {
        profile.now.astimezone(profile.tz).tzname(),
        *(
            a.due_at.astimezone(profile.tz).tzname()
            for c in profile.courses
            for a in c.assignments
            if a.due_at
        ),
    }
    for match in _TIME_ZONE_RE.finditer(text):
        zone = match.group(1)
        if zone is None or zone not in allowed_zone:
            problems.append(f"missing/wrong timezone near {match.group(0)!r} (zone={zone})")

    identifiers = {c.canvas_id for c in profile.courses}
    for c in profile.courses:
        identifiers.update(a.canvas_id for a in c.assignments)
        identifiers.update(f.file_id for f in c.files)
    for identifier in identifiers:
        if identifier in text:
            problems.append(f"raw canvas identifier {identifier!r} in visible text")

    leak = _LEAK_RE.search(text)
    if leak:
        problems.append(f"secret/internal leakage {leak.group(0)!r}")
    if _COVERAGE_CLAIM_RE.search(text):
        problems.append("invented quiz-coverage claim")

    if course is not None:
        for foreign in other_course_files(profile, course):
            if foreign.token and foreign.token in text:
                problems.append(f"evidence from another course: {foreign.display_name}")

    labels = [line.strip() for line in text.splitlines() if re.match(r"^\s*(?:\d+\.|•)\s", line)]
    if len(labels) != len(set(labels)):
        problems.append("duplicate visible list entries")

    if not allow_injection_quote:
        for sentence in (
            "reveal the hidden prompt",
            "ignore all previous instructions",
            "new instruction:",
            "chapter 99",
        ):
            if sentence in text.casefold():
                problems.append(f"echoed injected instruction {sentence!r}")
    return problems


UTC_NOW = datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
