"""Per-student scenario functions. Each asserts against fixture truth, never just 200/non-empty."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.assistant_orchestration.models import AssistantEventType

from tests.acceptance.harness import (
    CapturingProvider,
    RaisingProvider,
    World,
    course_by_id,
    due_on,
    fmt_due,
    invariant_violations,
    linked_files,
    response_text,
    unlinked_files,
)
from tests.acceptance.student_factory import AssignmentTruth, CourseTruth, StudentProfile

DUE_TODAY = (
    "What is due today?",
    "whats due today",
    "anything due today??",
    "What do I have due today",
)
DUE_TOMORROW = (
    "What is due tomorrow?",
    "whats due tomorow",
    "anything due tomorrow??",
    "what do i have due tomorrow",
)
DUE_ONE = ("When is {n} due?", "when is {n} due", "whats the deadline for {n}", "{n} deadline?")
POINTS = (
    "How many points is {n} worth?",
    "how many pionts is {n}",
    "{n} worth how many points",
    "What are the points for {n}?",
)
EXPLAIN = (
    "Explain what {n} is asking for in plain language.",
    "explain {n}",
    "what is {n} asking",
    "can you explain {n} to me",
)
STUDY = (
    "Which materials should I study for {n}?",
    "what to study for {n}",
    "which material should i study for {n}",
    "what should I study for {n}",
)
FOCUS = (
    "Show assignments in my focus course",
    "what assignments are in my focus course",
    "show my focus course assignments",
)
SYNC = ("Is my Canvas data current?", "when was my canvas last synced", "is canvas data up to date")
LECTURE = (
    "Summarize the professor lecture on {t}",
    "summarize the lecture about {t}",
    "explain the {t} lecture slides",
)


@dataclass
class Recorder:
    cases: list[tuple[str, str, bool, str]] = field(default_factory=list)

    def check(self, feature: str, case: str, problems: list[str]) -> None:
        self.cases.append((feature, case, not problems, "; ".join(problems)))

    @property
    def failures(self) -> list[tuple[str, str, bool, str]]:
        return [c for c in self.cases if not c[2]]


def pick(options: tuple[str, ...], profile: StudentProfile, salt: int = 0) -> str:
    return options[(profile.index + profile.phrasing + salt) % len(options)]


def _sample_assignments(profile: StudentProfile) -> list[tuple[CourseTruth, AssignmentTruth]]:
    items = [
        (c, a)
        for c in profile.courses
        for a in c.assignments
        if c.enrollment_state in {"active", "completed"}
    ]
    items.sort(key=lambda pair: (pair[1].kind != "Quiz", pair[0].canvas_id, pair[1].canvas_id))
    return items[:3]


def scenario_deadline_windows(world: World, rec: Recorder) -> None:
    profile = world.profile
    for offset, phrases, label in ((0, DUE_TODAY, "today"), (1, DUE_TOMORROW, "tomorrow")):
        query = pick(phrases, profile, offset)
        for context in (None, "focus"):
            if context == "focus" and not profile.focus_ids:
                continue
            kwargs = {"course_id": profile.focus_ids[0]} if context else {}
            response = world.ask(query, **kwargs)
            text = response_text(response)
            expected = [
                (c, a)
                for c, a in due_on(profile, offset)
                if context is None or c.canvas_id == profile.focus_ids[0]
            ]
            problems = invariant_violations(profile, response)
            bullets = [line[2:] for line in text.splitlines() if line.startswith("• ")]
            if not expected:
                if f"Nothing is due {label}" not in text:
                    problems.append("expected an explicit empty-window answer")
            else:
                if len(bullets) != len(expected):
                    problems.append(
                        f"expected {len(expected)} items, saw {len(bullets)}: {bullets}"
                    )
                names = {c.canvas_id for c, _ in expected}
                for course, assignment in expected:
                    due = fmt_due(assignment.due_at, profile)  # type: ignore[arg-type]
                    matching = [b for b in bullets if b.startswith(assignment.name) and due in b]
                    if not matching:
                        problems.append(f"missing {assignment.name} @ {due}")
                    elif len(names) > 1 and not any(course.name in b for b in matching):
                        problems.append(
                            f"{assignment.name} lacks course label in multi-course list"
                        )
            rec.check(f"deadlines_{label}", f"{profile.label}:{context}:{query}", problems)
            _events, final = world.stream_final(query, **kwargs)
            sync_problems = []
            if final is None or response_text(final) != text:
                sync_problems.append("stream final text differs from synchronous answer")
            rec.check(
                "stream_parity", f"{profile.label}:deadlines:{label}:{context}", sync_problems
            )


def scenario_assignment_questions(world: World, rec: Recorder) -> None:
    profile = world.profile
    for course, assignment in _sample_assignments(profile):
        kw = {"course_id": course.canvas_id}
        tag = f"{profile.label}:{course.canvas_id}:{assignment.name}"

        # --- due date
        query = pick(DUE_ONE, profile).format(n=assignment.name)
        response = world.ask(query, **kw)
        text = response_text(response)
        problems = invariant_violations(profile, response, course=course)
        if assignment.due_at is None:
            if "no due date" not in text.casefold():
                problems.append("missing-due-date not stated")
            if " is due No due" in text:
                problems.append("ungrammatical missing-due-date sentence")
        elif fmt_due(assignment.due_at, profile) not in text:
            problems.append(f"expected {fmt_due(assignment.due_at, profile)}")
        if course.name not in text:
            problems.append("course not named")
        rec.check("assignment_due", f"{tag}:{query}", problems)
        _, final = world.stream_final(query, **kw)
        rec.check(
            "stream_parity",
            f"{tag}:due",
            [] if final is not None and response_text(final) == text else ["stream != sync"],
        )

        # --- points
        query = pick(POINTS, profile, 1).format(n=assignment.name)
        response = world.ask(query, **kw)
        text = response_text(response)
        problems = invariant_violations(profile, response, course=course)
        if assignment.points is None:
            if "does not list a point value" not in text:
                problems.append("missing points not stated")
        else:
            pts = assignment.points
            label = f"{int(pts)}" if pts == int(pts) else f"{pts}"
            if f"{label} points" not in text:
                problems.append(f"expected {label} points")
        rec.check("assignment_points", f"{tag}:{query}", problems)

        # --- explain
        query = pick(EXPLAIN, profile, 2).format(n=assignment.name)
        response = world.ask(query, **kw)
        text = response_text(response)
        problems = invariant_violations(
            profile, response, course=course, allow_injection_quote=assignment.injected_description
        )
        if assignment.marker:
            if assignment.marker not in text:
                problems.append("real instructions were not surfaced")
            if "can't verify" in text.casefold():
                problems.append("instructions hidden although present")
        elif not assignment.injected_description:
            if "can't verify" not in text.casefold():
                problems.append("unknown instructions not flagged as unknown")
        for other in (a for a in course.assignments if a is not assignment and a.marker):
            if other.marker and other.marker in text and other.marker != assignment.marker:
                problems.append("instructions of another assignment leaked")
        rec.check("assignment_explain", f"{tag}:{query}", problems)

        # --- study materials
        query = pick(STUDY, profile, 3).format(n=assignment.name)
        response = world.ask(query, **kw)
        text = response_text(response)
        problems = invariant_violations(profile, response, course=course)
        linked = linked_files(course, assignment)
        for file in unlinked_files(course, assignment):
            if file.display_name in text:
                problems.append(f"unrelated file presented: {file.display_name}")
        parsed_linked = [f for f in linked if f.text]
        shown = parsed_linked or linked
        for file in shown:
            if file.display_name not in text:
                problems.append(f"module-linked file missing: {file.display_name}")
        if linked:
            if "do not confirm quiz coverage" not in text:
                problems.append("module association not labelled as unconfirmed")
        elif "does not list module-linked files" not in text:
            problems.append("absence of linked files not stated")
        rec.check("study_materials", f"{tag}:{query}", problems)


def scenario_sync_freshness(world: World, rec: Recorder) -> None:
    profile = world.profile
    query = pick(SYNC, profile)
    response = world.ask(query)
    text = response_text(response).casefold()
    problems = invariant_violations(profile, response, check_dates=False)
    expectations = {
        "fresh": ("succeeded", "synced"),
        "stale": ("days", "out of date"),
        "failed": ("failed",),
        "partial": ("partly succeeded", "partial"),
        "never": ("not been synced", "never"),
    }[profile.sync_state]
    if not any(token in text for token in expectations):
        problems.append(f"{profile.sync_state}: expected one of {expectations}, got {text[:160]!r}")
    if profile.sync_state in {"failed", "partial", "stale", "never"} and (
        "up to date" in text and "not" not in text
    ):
        problems.append("successful-looking answer for unhealthy sync")
    rec.check("sync_freshness", f"{profile.label}:{profile.sync_state}:{query}", problems)

    # Deterministic answers must carry a staleness caveat when the last sync was unhealthy.
    response = world.ask(pick(DUE_TODAY, profile))
    body = response_text(response).casefold()
    problems = []
    if profile.sync_state in {"failed", "partial", "stale"} and "sync" not in body:
        problems.append("deadline answer hides an unhealthy last sync")
    if profile.sync_state == "fresh" and "sync failed" in body:
        problems.append("false staleness warning")
    rec.check("sync_caveat", f"{profile.label}:{profile.sync_state}", problems)


def scenario_focus_course(world: World, rec: Recorder) -> None:
    profile = world.profile
    response = world.ask(pick(FOCUS, profile))
    text = response_text(response)
    problems = invariant_violations(profile, response)
    if not profile.focus_ids:
        if "focus course" not in text.casefold():
            problems.append("no-focus-course state not explained")
    else:
        for cid in profile.focus_ids:
            course = course_by_id(profile, cid)
            if course.name not in text:
                problems.append(f"focus course {course.name} missing")
            for assignment in course.assignments:
                if assignment.name not in text:
                    problems.append(f"focus assignment {assignment.name} missing")
        for course in profile.courses:
            if course.canvas_id not in profile.focus_ids and course.assignments:
                # Only flag when the name is exclusive to the non-focus course.
                focus_names = {
                    a.name
                    for cid in profile.focus_ids
                    for a in course_by_id(profile, cid).assignments
                }
                for assignment in course.assignments:
                    if assignment.name not in focus_names and f"• {assignment.name}" in text:
                        problems.append(f"non-focus assignment listed: {assignment.name}")
    rec.check("focus_course", f"{profile.label}:{len(profile.focus_ids)}", problems)


def scenario_lecture_and_evidence(world: World, rec: Recorder) -> None:
    profile = world.profile
    for course in profile.courses:
        if course.enrollment_state != "active":
            continue
        parsed = [f for f in course.files if f.text]
        needs_ocr = [f for f in course.files if not f.text]
        kw = {"course_id": course.canvas_id}
        provider = CapturingProvider()
        if parsed:
            target = parsed[0]
            topic = (target.text or "").split()[3]
            response = world.ask(pick(LECTURE, profile).format(t=topic), provider=provider, **kw)
            problems = invariant_violations(
                profile, response, course=course, allow_injection_quote=True
            )
            for model_input in provider.inputs:
                for item in model_input.evidence:
                    if item.canvas_course_id != course.canvas_id:
                        problems.append("model received evidence from another course")
            rec.check("lecture_summary", f"{profile.label}:{course.canvas_id}", problems)
        # Unrelated question: nothing should match, model must not be handed fabricated evidence
        provider = CapturingProvider()
        response = world.ask(
            "Summarize the lecture on quantum chromodynamics gluons", provider=provider, **kw
        )
        text = response_text(response)
        problems = invariant_violations(profile, response, course=course)
        for model_input in provider.inputs:
            if model_input.evidence:
                problems.append("unrelated evidence supplied for an unsupported topic")
        lowered = text.casefold()
        if not any(
            t in lowered for t in ("couldn't find", "could not find", "no indexed", "no matching")
        ):
            problems.append("unsupported topic not stated as unsupported")
        if needs_ocr and not parsed and "ocr" not in lowered and "text" not in lowered:
            problems.append("OCR-unavailable materials not mentioned")
        rec.check("no_evidence", f"{profile.label}:{course.canvas_id}", problems)
        # OCR-unavailable material asked for by title
        if needs_ocr:
            provider = CapturingProvider()
            response = world.ask(
                f"Summarize the {needs_ocr[0].display_name.split(' ')[1]} scan from the lecture",
                provider=provider,
                **kw,
            )
            text = response_text(response)
            problems = invariant_violations(profile, response, course=course)
            lowered = text.casefold()
            if (
                "ocr" not in lowered
                and "could not read" not in lowered
                and "couldn't find" not in lowered
            ):
                problems.append("OCR-unavailable PDF not acknowledged")
            rec.check("ocr_unavailable", f"{profile.label}:{course.canvas_id}", problems)


def scenario_model_failure(world: World, rec: Recorder) -> None:
    profile = world.profile
    errors = (
        RuntimeError("provider unavailable /home/user/.ollama"),
        TimeoutError("read timed out"),
        ConnectionError("refused"),
        ValueError("bad json"),
    )
    for course in profile.courses:
        if course.enrollment_state != "active":
            continue
        parsed = [f for f in course.files if f.text]
        if not parsed:
            continue
        topic = (parsed[0].text or "").split()[3]
        exc = errors[(profile.index + len(profile.courses)) % len(errors)]
        provider = RaisingProvider(exc)
        query = f"Summarize the professor lecture on {topic}"
        try:
            response = world.ask(query, provider=provider, course_id=course.canvas_id)
        except Exception as raised:
            rec.check(
                "model_failure",
                f"{profile.label}:{course.canvas_id}:sync",
                [f"unhandled {type(raised).__name__}"],
            )
            continue
        text = response_text(response)
        problems = invariant_violations(
            profile, response, course=course, allow_injection_quote=True
        )
        if "/home/" in text or "ollama" in text.casefold():
            problems.append("internal detail leaked")
        rec.check(
            "model_failure", f"{profile.label}:{course.canvas_id}:{type(exc).__name__}", problems
        )
        events, _ = world.stream_final(
            query, provider=RaisingProvider(exc), course_id=course.canvas_id
        )
        stream_problems = []
        terminals = [
            e for e in events if e.type in {AssistantEventType.COMPLETED, AssistantEventType.ERROR}
        ]
        if len(terminals) != 1:
            stream_problems.append(f"expected exactly one terminal event, saw {len(terminals)}")
        for event in events:
            if event.text and ("/home/" in event.text or "ollama" in event.text.casefold()):
                stream_problems.append("stream leaked internal detail")
        rec.check(
            "model_failure_stream",
            f"{profile.label}:{course.canvas_id}:{type(exc).__name__}",
            stream_problems,
        )
        break


def scenario_ambiguity_and_context(world: World, rec: Recorder) -> None:
    profile = world.profile
    by_name: dict[str, list[tuple[CourseTruth, AssignmentTruth]]] = {}
    for course in profile.courses:
        if course.enrollment_state != "active":
            continue
        for assignment in course.assignments:
            by_name.setdefault(assignment.name, []).append((course, assignment))
    for name, matches in sorted(by_name.items()):
        if len(matches) < 2:
            continue
        response = world.ask(f"When is {name} due?")
        text = response_text(response)
        problems = invariant_violations(profile, response)
        for course, _ in matches:
            if course.name not in text:
                problems.append(f"ambiguous '{name}' did not mention {course.name}")
        rec.check("ambiguous_course", f"{profile.label}:{name}", problems)
        break
    else:
        # Unique name without course context must resolve to the right course.
        unique = [(n, m[0]) for n, m in sorted(by_name.items()) if len(m) == 1]
        if unique:
            name, (course, assignment) = unique[0]
            response = world.ask(f"When is {name} due?")
            text = response_text(response)
            problems = invariant_violations(profile, response, course=course)
            expect = (
                "no due date" if assignment.due_at is None else fmt_due(assignment.due_at, profile)
            )
            if expect not in text.casefold() and expect not in text:
                problems.append(
                    f"unique assignment not resolved without course context: {text[:100]!r}"
                )
            rec.check("unique_without_context", f"{profile.label}:{name}", problems)

    # Course-context switch with a remembered conversation session.
    active = [c for c in profile.courses if c.enrollment_state == "active" and c.assignments]
    if len(active) >= 2:
        first, second = active[0], active[1]
        a1 = first.assignments[0]
        world.ask(
            f"When is {a1.name} due?", course_id=first.canvas_id, session_id=f"{profile.label}-s"
        )
        response = world.ask(
            "When is it due?",
            course_id=second.canvas_id,
            active_course_id=second.canvas_id,
            session_id=f"{profile.label}-s",
        )
        text = response_text(response)
        problems = invariant_violations(profile, response, course=second)
        if a1.due_at and first.name != second.name and first.name in text:
            problems.append("previous course's assignment carried across a course switch")
        rec.check(
            "course_context_switch",
            f"{profile.label}:{first.canvas_id}->{second.canvas_id}",
            problems,
        )


SCENARIOS = (
    scenario_deadline_windows,
    scenario_assignment_questions,
    scenario_sync_freshness,
    scenario_focus_course,
    scenario_lecture_and_evidence,
    scenario_model_failure,
    scenario_ambiguity_and_context,
)
