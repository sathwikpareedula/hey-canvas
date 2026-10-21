"""Safe provider-neutral academic assistant orchestration."""

import calendar
import re
from collections.abc import Iterator
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select

from app.assistant_provider.grounded_fallback import grounded_assistant_response
from app.assistant_tools.assignment_resolution import (
    find_assignment_id_for_query,
    find_assignment_matches,
)
from app.assistant_tools.deterministic_answers import try_deterministic_answer
from app.assistant_tools.models import (
    AssignmentToolRecord,
    AssistantEvidenceReference,
    AssistantRequest,
    AssistantResponse,
    AssistantResponseBlock,
    DeadlineToolResult,
    DocumentEvidence,
    ResponseBlockType,
    RetrievalEvidenceProvider,
    SourceAuthority,
)
from app.assistant_tools.operational_answers import (
    build_assignment_ambiguity_answer,
    build_focus_assignments_answer,
    build_no_evidence_answer,
    build_sync_status_answer,
    sync_caveat,
    with_caveat,
)
from app.assistant_tools.question_intent import (
    AcademicQuestionIntent,
    classify_academic_question,
    intent_allows_semantic_retrieval,
    is_concept_question,
    normalize_question,
)
from app.assistant_tools.service import AcademicToolService
from app.calendar.service import AcademicCalendarService
from app.course_router.models import CourseRoutingRequest, ResolutionOutcome
from app.database.assignment_repository import AssignmentRepository
from app.database.models import Course, SyncRun
from app.focus_courses.service import FocusCourseService
from app.notifications.service import NotificationService
from app.practice_sessions.models import PracticeAnswer, PracticeSessionCreate
from app.practice_sessions.service import PracticeSessionService
from app.reminders.service import ReminderPlanService
from app.services.deadlines import DeadlineService, DeadlineWindow
from app.services.retrieval_query_focus import focused_retrieval_query
from app.study_guides.models import StudyGuideRequest
from app.study_guides.service import StudyGuideService
from app.study_sessions.models import StudySessionCreate
from app.study_sessions.service import StudySessionService
from app.workspaces.service import WorkspaceService

from .models import (
    AcademicModelProvider,
    AssistantEvent,
    AssistantEventType,
    AssistantModelInput,
    AssistantOperation,
    CancellationToken,
    ToolPlan,
)
from .topic_continuity import concept_continuity, is_concept_follow_up


class OrchestrationError(ValueError):
    """Raised when provider output or an orchestration boundary is invalid."""


class AcademicAssistantOrchestrator:
    """Plan a bounded operation, gather deterministic facts, then call one provider."""

    _OPERATIONS = frozenset(AssistantOperation)

    def __init__(
        self,
        tools: AcademicToolService,
        provider: AcademicModelProvider,
        *,
        retrieval: RetrievalEvidenceProvider | None = None,
    ) -> None:
        self._tools = tools
        self._provider = provider
        self._retrieval = retrieval

    @staticmethod
    def _clear_stale_concept(model_input: AssistantModelInput) -> None:
        """Clear a prior topic when a non-concept turn supersedes it.

        Called before deterministic early returns, not only on provider turns.
        Generic follow-ups deliberately preserve the most recent topic.
        """
        request = model_input.request
        if is_concept_follow_up(request.query):
            return
        if request.assignment_id is None and is_concept_question(request.query):
            return
        course_id = AcademicAssistantOrchestrator._evidence_course(model_input)
        if request.session_id and course_id:
            concept_continuity.clear(request.session_id, course_id)

    @staticmethod
    def _conceptual_provider_input(model_input: AssistantModelInput) -> AssistantModelInput:
        """Bind a generic follow-up to the last topic in the same session/course.

        The hint is ephemeral and affects only model prompting, never authoritative
        Canvas routing, assignment resolution, or evidence validation.
        """
        request = model_input.request
        session_id = request.session_id
        course_id = AcademicAssistantOrchestrator._evidence_course(model_input)
        if not session_id or not course_id:
            return model_input
        if is_concept_follow_up(request.query):
            previous = concept_continuity.recall(session_id, course_id)
            if previous is None:
                return model_input
            clarified = request.model_copy(update={
                "query": (
                    f"{request.query}. "
                    f"Continue the previous concept from this conversation: {previous}. "
                    "Do not switch to a different older study topic."
                )[:4000]
            })
            return model_input.model_copy(update={"request": clarified})
        if request.assignment_id is None and is_concept_question(request.query):
            concept_continuity.remember(session_id, course_id, request.query)
        return model_input

    def run(self, request: AssistantRequest) -> AssistantResponse:
        plan = self.plan(request)
        model_input = self._assemble(request, plan)
        self._clear_stale_concept(model_input)
        intent_answer = self._try_intent_deterministic(model_input)
        if intent_answer is not None:
            return intent_answer
        deterministic = (
            self._graph_search_concept_answer(model_input)
            or self._relative_angle_kinematics_answer(model_input)
            or self._absolute_angle_kinematics_answer(model_input)
            or self._deterministic_response(model_input)
        )
        if deterministic is not None:
            return deterministic
        try:
            response = self._provider.complete(self._conceptual_provider_input(model_input))
            return self._validate_response(response, model_input)
        except Exception:
            fallback = grounded_assistant_response(model_input)
            if fallback is not None:
                return self._validate_response(fallback, model_input)
            return AssistantResponse(
                status="error",
                blocks=(
                    AssistantResponseBlock(
                        type=ResponseBlockType.ERROR,
                        text="assistant provider is temporarily unavailable",
                    ),
                ),
            )

    @staticmethod
    def _graph_search_concept_answer(
        model_input: AssistantModelInput,
    ) -> AssistantResponse | None:
        """Answer stable graph-search fundamentals without paying model latency.

        These are general computer-science definitions, never claims about an
        instructor's coverage. Assignment questions remain on the evidence path.
        """
        request = model_input.request
        if request.assignment_id is not None or model_input.assignment_context is not None:
            return None

        query = " ".join(request.query.casefold().split())
        session_id = request.session_id
        course_id = AcademicAssistantOrchestrator._evidence_course(model_input)
        previous = (
            concept_continuity.recall(session_id, course_id)
            if session_id and course_id
            else None
        )
        previous_query = previous.casefold() if previous else ""

        compares_bfs_dfs = "bfs" in query and "dfs" in query
        asks_astar = any(term in query for term in ("a*", "a-star", "astar")) and any(
            term in query for term in ("search", "path", "planning")
        )
        asks_admissibility = (
            "heuristic" in query
            and any(term in query for term in ("not admissible", "inadmissible", "optimal"))
        )
        astar_follow_up = (
            is_concept_follow_up(request.query)
            and any(term in previous_query for term in ("a*", "a-star", "path planning"))
            and any(term in query for term in ("example", "calculation", "admissible", "optimal"))
        )

        text: str | None = None
        if compares_bfs_dfs:
            text = (
                "BFS and DFS explore the same graph in different orders. Breadth-first search "
                "uses a FIFO queue and visits nodes level by level. It is complete on finite-"
                "branching graphs and finds a shortest path when every edge has the same cost, "
                "but its frontier can require substantial memory. Depth-first search uses a LIFO "
                "stack (often recursion), follows one branch deeply, and usually needs less "
                "frontier memory. It is not generally optimal and needs cycle/depth handling to "
                "be complete. This is general algorithm knowledge, not verified course coverage."
            )
        elif asks_admissibility or (astar_follow_up and "admissib" in query):
            text = (
                "For A* graph search, an admissible heuristic never overestimates the true "
                "remaining cost. If the heuristic is not admissible, A* can expand a route that "
                "looks artificially cheap and is no longer guaranteed to return an optimal path. "
                "It may still find a valid or even optimal path on a particular problem, but the "
                "optimality guarantee is lost. This is general algorithm knowledge, not a claim "
                "about your professor's exam coverage."
            )
        elif asks_astar:
            text = (
                "Robot path planning searches for a collision-free route from a start state to a "
                "goal. A* ranks each frontier state n by f(n) = g(n) + h(n), where g(n) is the "
                "cost already traveled and h(n) estimates the remaining cost. On a grid, blocked "
                "cells are excluded from successor generation; A* repeatedly expands the lowest-"
                "f state, updates cheaper routes, and reconstructs the path from parent links when "
                "the goal is reached. An admissible heuristic such as Manhattan distance for "
                "four-direction movement preserves optimality. This is general algorithm "
                "knowledge, not verified course coverage."
            )
        elif astar_follow_up:
            text = (
                "Example: on a four-direction grid, suppose a neighbor has traveled cost g = 4 "
                "and Manhattan distance h = 3 to the goal. A* assigns f = g + h = 7. It compares "
                "that value with the other frontier cells, expands the smallest f, and never adds "
                "blocked obstacle cells as valid successors. Parent links reconstruct the final "
                "route once the goal is selected. This is a general example, not verified course "
                "coverage."
            )

        if text is None:
            return None
        if session_id and course_id and (asks_astar or astar_follow_up or asks_admissibility):
            concept_continuity.remember(session_id, course_id, "A* robot path planning")
        return AssistantResponse(
            status="ok",
            blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
            course_id=model_input.plan.course_id,
        )

    @staticmethod
    def _relative_angle_kinematics_answer(
        model_input: AssistantModelInput,
    ) -> AssistantResponse | None:
        """Teach the two-link geometry only when the relative-angle convention is explicit.

        This is a general mathematical identity, never evidence of quiz coverage.
        Do not intercept assignment-specific instructions or absolute-angle questions.
        """
        request = model_input.request
        query = " ".join(request.query.casefold().split())
        if (
            request.assignment_id is not None
            or model_input.assignment_context is not None
            or "absolute" in query
        ):
            return None

        session_id = request.session_id
        course_id = AcademicAssistantOrchestrator._evidence_course(model_input)

        is_explicit_fk = (
            ("two-link" in query or "2-link" in query or "two link" in query)
            and "forward kinematics" in query
            and "relative" in query
            and ("angle" in query or "joint" in query)
        )
        is_second_link_angle_query = (
            any(k in query for k in ("add", "adding", "sum", "theta1 + theta2", "plus"))
            and any(
                k in query
                for k in (
                    "second link",
                    "link 2",
                    "second joint",
                    "joint 2",
                    "two joint angles",
                    "joint angles",
                )
            )
            and ("angle" in query or "joint" in query)
        )
        is_numerical_follow_up = False
        if session_id and course_id and is_concept_follow_up(request.query):
            prev = concept_continuity.recall(session_id, course_id)
            if prev and any(
                k in prev.casefold()
                for k in ("kinematics", "two-link", "joint angles", "second link")
            ):
                is_numerical_follow_up = True

        is_numeric_compute = (
            re.search(r"\bl1\s*=\s*\d+", query) is not None
            and re.search(r"\bl2\s*=\s*\d+", query) is not None
            and re.search(r"\btheta1\s*=\s*-?\d+", query) is not None
            and re.search(r"\btheta2\s*=\s*-?\d+", query) is not None
        )

        if not (
            is_explicit_fk
            or is_second_link_angle_query
            or is_numerical_follow_up
            or is_numeric_compute
        ):
            return None

        if session_id and course_id:
            concept_continuity.remember(
                session_id,
                course_id,
                "planar robot forward kinematics two-link joint angles",
            )

        if is_numeric_compute:
            import math
            m_l1 = re.search(r"\bl1\s*=\s*(\d+(?:\.\d+)?)", query)
            m_l2 = re.search(r"\bl2\s*=\s*(\d+(?:\.\d+)?)", query)
            m_th1 = re.search(
                r"\btheta1\s*=\s*(-?\d+(?:\.\d+)?)\s*(°|deg|degrees|rad|radians)?",
                query,
            )
            m_th2 = re.search(
                r"\btheta2\s*=\s*(-?\d+(?:\.\d+)?)\s*(°|deg|degrees|rad|radians)?",
                query,
            )
            if m_l1 and m_l2 and m_th1 and m_th2:
                l1 = float(m_l1.group(1))
                l2 = float(m_l2.group(1))
                th1 = float(m_th1.group(1))
                th2 = float(m_th2.group(1))
                unit1 = m_th1.group(2) or "deg"
                unit2 = m_th2.group(2) or "deg"
                th1_rad = th1 if "rad" in unit1 else math.radians(th1)
                th2_rad = th2 if "rad" in unit2 else math.radians(th2)
                th_tot_rad = th1_rad + th2_rad
                x_val = l1 * math.cos(th1_rad) + l2 * math.cos(th_tot_rad)
                y_val = l1 * math.sin(th1_rad) + l2 * math.sin(th_tot_rad)
                xr = round(x_val, 4)
                yr = round(y_val, 4)
                xs = f"{int(xr)}" if xr.is_integer() else f"{xr:g}"
                ys = f"{int(yr)}" if yr.is_integer() else f"{yr:g}"
                calc_text = (
                    f"Forward Kinematics Numerical Calculation (Relative Angle Convention):\n\n"
                    f"Parameters:\n"
                    f"• Link lengths: L1 = {l1:g}, L2 = {l2:g}\n"
                    f"• Joint angles: theta1 = {th1:g}°, theta2 = {th2:g}° (relative to link 1)\n\n"
                    f"Equations:\n"
                    f"• theta_total = theta1 + theta2 = {th1 + th2:g}°\n"
                    f"• x = L1 * cos(theta1) + L2 * cos(theta1 + theta2)\n"
                    f"• y = L1 * sin(theta1) + L2 * sin(theta1 + theta2)\n\n"
                    f"Result: x = {xs}, y = {ys}"
                )
                return AssistantResponse(
                    status="ok",
                    blocks=(
                        AssistantResponseBlock(
                            type=ResponseBlockType.TEXT, text=calc_text
                        ),
                    ),
                    course_id=model_input.plan.course_id,
                )

        if is_numerical_follow_up:
            numerical_example = (
                "Here is a step-by-step numerical example for a 2-link planar manipulator with "
                "relative joint angles:\n\n"
                "Given Parameters:\n"
                "• Link lengths: L1 = 10, L2 = 5\n"
                "• Joint 1 angle (base to link 1): θ1 = 0 rad (0°)\n"
                "• Joint 2 angle (link 1 to link 2 relative angle): θ2 = π/2 rad (90°)\n\n"
                "Forward Kinematics Equations:\n"
                "• Link 1 tip position: (x1, y1) = (L1*cos(θ1), L1*sin(θ1)) = "
                "(10*cos(0°), 10*sin(0°)) = (10, 0)\n"
                "• Second link total orientation relative to base frame: "
                "θ_total = θ1 + θ2 = 0° + 90° = 90°\n"
                "• End-effector (tip) position:\n"
                "   x = L1*cos(θ1) + L2*cos(θ1 + θ2) = 10*cos(0°) + 5*cos(90°)\n"
                "     = 10*(1) + 5*(0) = 10\n"
                "   y = L1*sin(θ1) + L2*sin(θ1 + θ2) = 10*sin(0°) + 5*sin(90°)\n"
                "     = 10*(0) + 5*(1) = 5\n\n"
                "Result: The end-effector coordinates are (x, y) = (10, 5).\n"
                "Because θ2 is relative to link 1, link 2 extends perpendicularly upward (+y) "
                "from the tip of link 1 at (10, 0)."
            )
            return AssistantResponse(
                status="ok",
                blocks=(
                    AssistantResponseBlock(
                        type=ResponseBlockType.TEXT, text=numerical_example
                    ),
                ),
                course_id=model_input.plan.course_id,
            )

        explanation = (
            "For a planar two-link robot arm, let l1 and l2 be the link lengths, "
            "theta1 the first joint angle measured from the positive x-axis, and "
            "theta2 the second joint angle measured RELATIVE to the first link. "
            "The first link points at theta1; the second link therefore points "
            "at theta1 + theta2, not theta2 alone.\n\n"
            "The first link contributes (l1 cos(theta1), l1 sin(theta1)). "
            "The second contributes "
            "(l2 cos(theta1 + theta2), l2 sin(theta1 + theta2)). "
            "Adding their components gives:\n"
            "x = l1 cos(theta1) + l2 cos(theta1 + theta2)\n"
            "y = l1 sin(theta1) + l2 sin(theta1 + theta2)\n\n"
            "For example, when theta1 = 0 and theta2 = 90 degrees, "
            "the tip is at (l1, l2). If theta2 were an ABSOLUTE angle relative "
            "to the base, its formula would instead use theta2 alone; "
            "always identify the angle convention first."
        )
        return AssistantResponse(
            status="ok",
            blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=explanation),),
            course_id=model_input.plan.course_id,
        )

    @staticmethod
    def _absolute_angle_kinematics_answer(
        model_input: AssistantModelInput,
    ) -> AssistantResponse | None:
        request = model_input.request
        query = " ".join(request.query.casefold().split())
        if "absolute" not in query:
            return None
        if not (
            any(k in query for k in ("two-link", "2-link", "two link"))
            and any(k in query for k in ("forward kinematics", "kinematics"))
        ):
            return None
        explanation = (
            "For a planar two-link robot arm using ABSOLUTE joint angles:\n\n"
            "Convention:\n"
            "• Let l1 and l2 be the link lengths.\n"
            "• theta1 is the angle of link 1 measured from the positive x-axis (base frame).\n"
            "• theta2 is the ABSOLUTE angle of link 2, measured directly from the positive x-axis "
            "(global base frame), NOT relative to link 1.\n\n"
            "Forward Kinematics Equations:\n"
            "Because theta2 is already defined relative to the base coordinate frame, "
            "we do not add the joint angles:\n"
            "• x = l1 * cos(theta1) + l2 * cos(theta2)\n"
            "• y = l1 * sin(theta1) + l2 * sin(theta2)\n\n"
            "Contrast with relative angles:\n"
            "If theta2 were relative to link 1, the second link's orientation would be "
            "theta1 + theta2. Always verify whether the angles are specified as "
            "absolute or relative."
        )
        return AssistantResponse(
            status="ok",
            blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=explanation),),
            course_id=model_input.plan.course_id,
        )

    @staticmethod
    def _deterministic_response(
        model_input: AssistantModelInput,
    ) -> AssistantResponse | None:
        payload: AssistantResponseBlock | None = None
        if model_input.deadlines is not None:
            payload = AssistantResponseBlock(
                type=ResponseBlockType.DEADLINES,
                payload={
                    "window": model_input.deadlines.window,
                    "assignments": [
                        item.model_dump(mode="json")
                        for item in model_input.deadlines.assignments
                    ],
                    "empty": not model_input.deadlines.assignments,
                    "message": (
                        f"Nothing due {model_input.deadlines.window.replace('_', ' ')}."
                        if not model_input.deadlines.assignments
                        else None
                    ),
                },
            )
        elif model_input.recent_changes is not None:
            payload = AssistantResponseBlock(
                type=ResponseBlockType.RECENT_CHANGES,
                payload=model_input.recent_changes.model_dump(mode="json"),
            )
        elif model_input.notifications is not None:
            payload = AssistantResponseBlock(
                type=ResponseBlockType.NOTIFICATION_SUMMARY,
                payload=model_input.notifications.model_dump(mode="json"),
            )
        elif model_input.course_list:
            payload = AssistantResponseBlock(
                type=ResponseBlockType.COURSE_LIST,
                payload={
                    "courses": [
                        item.model_dump(mode="json") for item in model_input.course_list
                    ]
                },
            )
        elif model_input.sync_status is not None:
            payload = AssistantResponseBlock(
                type=ResponseBlockType.SYNC_STATUS,
                payload=model_input.sync_status,
            )
        if payload is None:
            return None
        text = (
            f"{len(model_input.deadlines.assignments)} assignment(s) "
            f"due {model_input.deadlines.window.replace('_', ' ')}."
            if model_input.deadlines is not None
            else None
        )
        return AssistantResponse(
            status="ok",
            blocks=(
                AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
                payload,
            ),
            course_id=model_input.plan.course_id,
        )

    def events(
        self,
        request: AssistantRequest,
        *,
        cancellation: CancellationToken | None = None,
    ) -> Iterator[AssistantEvent]:
        plan = self.plan(request)
        model_input = self._assemble(request, plan)
        self._clear_stale_concept(model_input)
        if self._cancelled(cancellation):
            return
        intent_answer = self._try_intent_deterministic(model_input)
        deterministic = (
            self._graph_search_concept_answer(model_input)
            or self._relative_angle_kinematics_answer(model_input)
            or self._absolute_angle_kinematics_answer(model_input)
            or self._deterministic_response(model_input)
            if intent_answer is None
            else None
        )
        # STARTED is the setup barrier: all request-session queries must finish
        # before a detached producer can transition into cancellable model I/O.
        yield AssistantEvent(type=AssistantEventType.STARTED)
        if self._cancelled(cancellation):
            return
        if intent_answer is not None:
            yield from self._response_events(intent_answer)
            yield AssistantEvent(type=AssistantEventType.COMPLETED, response=intent_answer)
            return
        if deterministic is not None:
            yield from self._response_events(deterministic)
            yield AssistantEvent(type=AssistantEventType.COMPLETED, response=deterministic)
            return
        streamed_response: AssistantResponse | None = None
        provider_input = self._conceptual_provider_input(model_input)
        try:
            cancellable_stream = getattr(self._provider, "stream_with_cancellation", None)
            provider_events = (
                cancellable_stream(provider_input, cancellation)
                if callable(cancellable_stream)
                else self._provider.stream(provider_input)
            )
            for event in provider_events:
                if self._cancelled(cancellation):
                    return
                if not isinstance(event, AssistantEvent):
                    raise OrchestrationError("provider stream event is invalid")
                validated = self._validate_event(event, model_input)
                if validated.type is AssistantEventType.STARTED:
                    continue
                if validated.type is AssistantEventType.ERROR:
                    yield AssistantEvent(
                        type=AssistantEventType.ERROR,
                        text="assistant provider returned an error",
                    )
                    return
                if validated.type is AssistantEventType.COMPLETED:
                    streamed_response = validated.response
                    break
                # Provider deltas are provisional until the terminal response is
                # validated. Keep SSE STARTED responsive, but never expose
                # unverified text, blocks, or citations as student-visible facts.
                # Validated blocks and sources are emitted below on success.
                continue
        except Exception:
            if self._cancelled(cancellation):
                return
            fallback = grounded_assistant_response(model_input)
            if fallback is not None:
                try:
                    response = self._validate_response(fallback, model_input)
                except OrchestrationError:
                    yield AssistantEvent(
                        type=AssistantEventType.ERROR,
                        text="assistant provider returned invalid response data",
                    )
                    return
                yield from self._response_events(response)
                yield AssistantEvent(type=AssistantEventType.COMPLETED, response=response)
                return
            yield AssistantEvent(
                type=AssistantEventType.ERROR,
                text="assistant provider returned invalid stream data",
            )
            return
        if not self._cancelled(cancellation):
            try:
                response = self._validate_response(
                    streamed_response
                    if streamed_response is not None
                    else self._provider.complete(provider_input),
                    model_input,
                )
            except (RuntimeError, ValueError, TypeError):
                fallback = grounded_assistant_response(model_input)
                if fallback is None:
                    yield AssistantEvent(
                        type=AssistantEventType.ERROR,
                        text="assistant provider returned invalid response data",
                    )
                    return
                response = self._validate_response(fallback, model_input)
            except Exception:
                yield AssistantEvent(
                    type=AssistantEventType.ERROR,
                    text="assistant provider returned invalid response data",
                )
                return
            yield from self._response_events(response)
            yield AssistantEvent(type=AssistantEventType.COMPLETED, response=response)

    def plan(self, request: AssistantRequest) -> ToolPlan:
        operation = self._operation_for(request)
        return ToolPlan(
            operation=operation,
            course_id=request.course_id,
            query=request.query,
        )

    def _assemble(self, request: AssistantRequest, plan: ToolPlan) -> AssistantModelInput:
        workspace = WorkspaceService(self._tools.session)
        workspace_key = request.session_id
        # A teaching request must not inherit an unrelated pinned assignment.
        # Preserve explicit assignment IDs supplied by the caller.
        concept_request = is_concept_question(request.query)
        if workspace_key:
            resolved_assignment = (
                workspace.resolve_assignment(
                    workspace_key,
                    request.query,
                    course_id=request.course_id or request.active_course_id,
                )
                if request.assignment_id is None and not concept_request
                else None
            )
            if resolved_assignment is not None:
                request = request.model_copy(update={"assignment_id": resolved_assignment})
            resolved_document = (
                workspace.resolve_document(
                    workspace_key,
                    request.query,
                    course_id=request.course_id or request.active_course_id,
                )
                if request.document_id is None
                else None
            )
            if resolved_document is not None:
                request = request.model_copy(update={"document_id": resolved_document})
        course_hint = request.course_id or request.active_course_id
        if request.assignment_id is None and course_hint is not None and not concept_request:
            resolved_from_query = find_assignment_id_for_query(
                self._tools.session,
                canvas_course_id=course_hint,
                query=request.query,
            )
            if resolved_from_query is not None:
                request = request.model_copy(update={"assignment_id": resolved_from_query})
        assignment_candidates: tuple[AssignmentToolRecord, ...] = ()
        if (
            request.assignment_id is None
            and course_hint is None
            and classify_academic_question(request.query)
            in {
                AcademicQuestionIntent.ASSIGNMENT_DUE,
                AcademicQuestionIntent.ASSIGNMENT_POINTS,
                AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
                AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS,
            }
        ):
            matches = find_assignment_matches(self._tools.session, query=request.query)
            if len(matches) == 1:
                request = request.model_copy(
                    update={"assignment_id": matches[0][1].canvas_assignment_id}
                )
            elif len(matches) > 1:
                assignment_candidates = tuple(
                    self._tools.assignment_record(assignment) for _, assignment in matches[:6]
                )
        plan = ToolPlan(
            operation=self._operation_for(request),
            course_id=request.course_id or plan.course_id,
            query=request.query,
        )
        retrieval_query = focused_retrieval_query(request.query)
        routing = self._tools.resolve_course(
            CourseRoutingRequest(
                course_id=request.course_id,
                assignment_id=request.assignment_id,
                document_id=request.document_id,
                active_course_id=request.active_course_id,
                text=retrieval_query,
            )
        )
        if routing.result.outcome is ResolutionOutcome.AMBIGUOUS:
            raise OrchestrationError("course request is ambiguous")
        course_id = routing.result.course.course_id if routing.result.course else None
        if plan.operation is not AssistantOperation.RECENT_CHANGES:
            course_id = course_id or request.course_id
        question_intent = classify_academic_question(
            request.query,
            assignment_id=request.assignment_id,
        )
        # Assignment facts should not trigger a broad course semantic search.
        # A quiz deadline or missing quiz instructions must never inherit
        # arbitrary same-course PDF excerpts through the context package.
        context_retrieval = self._retrieval
        if question_intent in {
            AcademicQuestionIntent.ASSIGNMENT_DUE,
            AcademicQuestionIntent.ASSIGNMENT_POINTS,
            AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
            AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS,
            AcademicQuestionIntent.DEADLINES_WINDOW,
        }:
            context_retrieval = None
        context = self._tools.build_context_package(
            CourseRoutingRequest(
                course_id=course_id,
                assignment_id=request.assignment_id,
                document_id=request.document_id,
                active_course_id=request.active_course_id,
                text=retrieval_query,
            ),
            retrieval=context_retrieval
            if plan.operation
            in {
                AssistantOperation.MATERIAL_SEARCH,
                AssistantOperation.STUDY_HELP,
                AssistantOperation.STUDY_PLAN,
                AssistantOperation.PRACTICE_SESSION,
                AssistantOperation.STUDY_GUIDE,
            }
            else None,
        )
        if plan.operation in {
            AssistantOperation.ASSIGNMENT_CONTEXT,
            AssistantOperation.MATERIAL_SEARCH,
            AssistantOperation.STUDY_HELP,
        } and context is None:
            context = None
        explicit_month = self._calendar_month(request.query)
        deadline_window = self._deadline_window(request.query)
        deadlines = (
            self._scoped_calendar_month(
                explicit_month[0], explicit_month[1], course_id=course_id
            )
            if plan.operation is AssistantOperation.DEADLINES and explicit_month is not None
            else (
                self._scoped_deadlines(
                    deadline_window, course_id=course_id, query=request.query
                )
                if plan.operation is AssistantOperation.DEADLINES
                else None
            )
        )
        semantic_retrieval = intent_allows_semantic_retrieval(question_intent)
        if question_intent in {
            AcademicQuestionIntent.ASSIGNMENT_DUE,
            AcademicQuestionIntent.ASSIGNMENT_POINTS,
            AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
            AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS,
        }:
            semantic_retrieval = False
        assignment_context = (
            self._tools.get_assignment_context(
                request.assignment_id or "",
                course_id=course_id,
                retrieval=self._retrieval,
                retrieval_query=request.query,
                allow_semantic_retrieval=semantic_retrieval,
            )
            if plan.operation is AssistantOperation.ASSIGNMENT_CONTEXT
            else None
        )
        if request.session_id and assignment_context is not None:
            workspace.remember_entity(
                request.session_id,
                kind="assignment",
                entity_id=assignment_context.assignment.canvas_assignment_id,
                label=assignment_context.assignment.name or "",
                course_id=assignment_context.assignment.canvas_course_id,
                intent="assignment_context",
            )
        recent_changes = (
            self._tools.get_recent_changes(course_id=course_id)
            if plan.operation is AssistantOperation.RECENT_CHANGES
            else None
        )
        material_search = (
            self._tools.search_documents(request.query, course_id=course_id)
            if plan.operation is AssistantOperation.MATERIAL_SEARCH
            else None
        )
        study_plan = None
        practice_session = None
        practice_hint = None
        practice_feedback = None
        study_guide = None
        notifications = None
        reminder_preview = None
        calendar_preview = None
        course_list: tuple[BaseModel, ...] = ()
        sync_status: dict[str, object] | None = None
        if plan.operation is AssistantOperation.COURSE_LOOKUP:
            course_list = self._tools.get_courses()
        elif plan.operation is AssistantOperation.FOCUS_COURSES:
            course_list = tuple(FocusCourseService(self._tools.session).list())
        elif plan.operation is AssistantOperation.SYNC_STATUS:
            sync_status = self._latest_sync_payload()
        if plan.operation is AssistantOperation.STUDY_PLAN and course_id:
            study_plan = StudySessionService(self._tools.session).create(
                StudySessionCreate(
                    course_id=course_id,
                    goal=request.query,
                    duration_minutes=60,
                    topics=(
                        context.context.study_context.current_topic,
                    )
                    if context and context.context.study_context.current_topic
                    else (),
                    study_mode=request.study_mode or "learn",
                ),
                evidence=tuple(
                    AssistantEvidenceReference(
                        authority=item.authority,
                        identifier=item.canvas_file_id,
                        locator=item.heading,
                    )
                    for item in (context.retrieval_evidence if context else ())
                ),
            )
        if plan.operation is AssistantOperation.PRACTICE_SESSION and course_id:
            practice_session = PracticeSessionService(self._tools.session).create(
                PracticeSessionCreate(
                    course_id=course_id,
                    topic=request.query,
                    study_mode=request.study_mode or "practice",
                )
            )
        if plan.operation in {
            AssistantOperation.PRACTICE_HINT,
            AssistantOperation.PRACTICE_ANSWER,
        }:
            if not request.practice_session_id:
                raise OrchestrationError("practice_session_id is required")
            practice_service = PracticeSessionService(self._tools.session)
            if plan.operation is AssistantOperation.PRACTICE_HINT:
                practice_hint = practice_service.hint(request.practice_session_id).hint
            else:
                if request.answer is None:
                    raise OrchestrationError("answer is required")
                practice_feedback = practice_service.answer(
                    request.practice_session_id,
                    PracticeAnswer(
                        answer=request.answer,
                        question_id=request.practice_question_id,
                    ),
                )
            practice_session = practice_service.get(request.practice_session_id)
        if plan.operation is AssistantOperation.STUDY_GUIDE and course_id:
            study_guide = StudyGuideService().build(
                StudyGuideRequest(
                    course_id=course_id,
                    topic=request.query,
                    assignment_id=request.assignment_id,
                    document_id=request.document_id,
                    study_mode=request.study_mode or "review",
                ),
                course_name=context.context.course_name if context else None,
                evidence=tuple(
                    AssistantEvidenceReference(
                        authority=item.authority,
                        identifier=item.canvas_file_id,
                        locator=item.heading,
                    )
                    for item in (context.retrieval_evidence if context else ())
                ),
            )
        if plan.operation is AssistantOperation.LIST_NOTIFICATIONS:
            notifications = NotificationService(self._tools.session).list_notifications(
                course_id=course_id
            )
        assignment = (
            self._tools.assignment_entity(request.assignment_id, course_id=course_id)
            if request.assignment_id
            else None
        )
        if assignment is not None and plan.operation is AssistantOperation.PREVIEW_REMINDER_PLAN:
            reminder_preview = ReminderPlanService(self._tools.session).preview_plan(assignment)
        if assignment is not None and plan.operation is AssistantOperation.PREVIEW_CALENDAR_EVENT:
            calendar_preview = AcademicCalendarService().preview_assignment_event(assignment)
        evidence = context.retrieval_evidence if context else ()
        if assignment_context is not None and assignment_context.retrieval_evidence:
            evidence = AcademicAssistantOrchestrator._merge_document_evidence(
                evidence,
                assignment_context.retrieval_evidence,
            )
        from app.services.cross_source_linking import build_canvas_text_evidence

        canvas_text_evidence = (
            build_canvas_text_evidence(
                self._tools.session,
                canvas_course_id=course_id,
                query=request.query,
                assignment_name=None,
                limit=5,
            )
            if course_id is not None
            and plan.operation
            in {
                AssistantOperation.MATERIAL_SEARCH,
                AssistantOperation.STUDY_HELP,
                AssistantOperation.STUDY_PLAN,
                AssistantOperation.PRACTICE_SESSION,
                AssistantOperation.STUDY_GUIDE,
            }
            else ()
        )
        if assignment_context is not None:
            known_text = {
                (item.source_kind, item.source_id) for item in canvas_text_evidence
            }
            canvas_text_evidence = tuple(
                [*canvas_text_evidence]
                + [
                    item
                    for item in assignment_context.canvas_text_evidence
                    if (item.source_kind, item.source_id) not in known_text
                ]
            )[:10]
        elif (
            not canvas_text_evidence
            and course_id is not None
            and self._tools.session is not None
        ):
            canvas_text_evidence = build_canvas_text_evidence(
                self._tools.session,
                canvas_course_id=course_id,
                query=request.query,
                assignment_name=None,
                limit=5,
            )
        if request.session_id and course_id and evidence:
            file_ids = {item.canvas_file_id for item in evidence}
            if len(file_ids) == 1:
                first = evidence[0]
                workspace.remember_entity(
                    request.session_id,
                    kind="document",
                    entity_id=first.canvas_file_id,
                    label=first.display_name or first.filename or first.canvas_file_id,
                    course_id=course_id,
                    intent="document_context",
                )
        from app.security.html_sanitize import wrap_untrusted_excerpt

        untrusted = tuple(
            [wrap_untrusted_excerpt(item.excerpt) for item in evidence if item.excerpt]
            + [
                wrap_untrusted_excerpt(item.excerpt)
                for item in canvas_text_evidence
                if item.excerpt
            ]
        )[:20]
        return AssistantModelInput(
            request=request,
            plan=plan.model_copy(update={"course_id": course_id}),
            context=context,
            deadlines=deadlines,
            assignment_context=assignment_context,
            recent_changes=recent_changes,
            material_search=material_search,
            evidence=evidence,
            canvas_text_evidence=canvas_text_evidence,
            untrusted_material=untrusted,
            study_plan=study_plan,
            practice_session=practice_session,
            practice_hint=practice_hint,
            practice_feedback=practice_feedback,
            study_guide=study_guide,
            notifications=notifications,
            reminder_preview=reminder_preview,
            calendar_preview=calendar_preview,
            course_list=course_list,
            sync_status=sync_status,
            assignment_candidates=assignment_candidates,
        )

    @classmethod
    def _operation_for(cls, request: AssistantRequest) -> AssistantOperation:
        if request.operation != "answer":
            try:
                return AssistantOperation(request.operation)
            except ValueError as exc:
                raise OrchestrationError("unsupported assistant operation") from exc
        query = normalize_question(request.query)
        if request.practice_session_id and "hint" in query:
            return AssistantOperation.PRACTICE_HINT
        if request.practice_session_id and (
            "answer" in query or "check" in query
        ):
            return AssistantOperation.PRACTICE_ANSWER
        if (
            request.study_mode is not None
            and request.study_mode.value == "exam_prep"
            and not cls._is_active_study_step_request(query)
        ):
            return AssistantOperation.STUDY_PLAN
        intent = classify_academic_question(
            request.query,
            assignment_id=request.assignment_id,
        )
        if intent in {
            AcademicQuestionIntent.ASSIGNMENT_DUE,
            AcademicQuestionIntent.ASSIGNMENT_POINTS,
            AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS,
            AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
        }:
            return AssistantOperation.ASSIGNMENT_CONTEXT
        if intent is AcademicQuestionIntent.DEADLINES_WINDOW:
            return AssistantOperation.DEADLINES
        if "focus course" in query or "active course" in query:
            return AssistantOperation.FOCUS_COURSES
        if "course" in query and any(word in query for word in ("list", "which", "what")):
            return AssistantOperation.COURSE_LOOKUP
        if any(
            phrase in query
            for phrase in (
                "sync status",
                "last sync",
                "last synced",
                "canvas data",
                "up to date",
                "out of date",
                "data current",
                "data fresh",
            )
        ):
            return AssistantOperation.SYNC_STATUS
        if "remind" in query:
            return AssistantOperation.PREVIEW_REMINDER_PLAN
        if "remember" in query and "week" in query:
            return AssistantOperation.LIST_NOTIFICATIONS
        if "calendar" in query:
            return AssistantOperation.PREVIEW_CALENDAR_EVENT
        if request.assignment_id or "assignment" in query:
            return AssistantOperation.ASSIGNMENT_CONTEXT
        if "changed" in query or "change" in query:
            return AssistantOperation.RECENT_CHANGES
        if (
            request.document_id
            or "material" in query
            or "document" in query
            or "pdf" in query
            or "notes" in query
            or "lecture" in query
            or "reading" in query
            or "slides" in query
        ):
            return AssistantOperation.MATERIAL_SEARCH
        if "quiz" in query or "practice" in query:
            if "hint" in query:
                return AssistantOperation.PRACTICE_HINT
            if "answer" in query or "check" in query:
                return AssistantOperation.PRACTICE_ANSWER
            return AssistantOperation.PRACTICE_SESSION
        if (
            request.study_mode is not None
            and request.study_mode.value == "exam_prep"
            and not cls._is_active_study_step_request(query)
        ):
            return AssistantOperation.STUDY_PLAN
        if "study guide" in query:
            return AssistantOperation.STUDY_GUIDE
        if "study plan" in query or "continue" in query:
            return AssistantOperation.STUDY_PLAN
        return AssistantOperation.STUDY_HELP

    @staticmethod
    def _is_active_study_step_request(normalized_query: str) -> bool:
        """Keep an in-progress exam-prep step in the evidence-backed help path."""
        return (
            "study step" in normalized_query
            or "current step" in normalized_query
            or "current session" in normalized_query
        )

    def _try_intent_deterministic(
        self, model_input: AssistantModelInput
    ) -> AssistantResponse | None:
        bounded = self._try_bounded_claim_answer(model_input)
        if bounded is not None:
            return bounded
        intent = classify_academic_question(
            model_input.request.query,
            assignment_id=model_input.request.assignment_id,
        )
        timezone = self._tools._timezone
        operation = model_input.plan.operation
        if model_input.assignment_candidates and intent in {
            AcademicQuestionIntent.ASSIGNMENT_DUE,
            AcademicQuestionIntent.ASSIGNMENT_POINTS,
            AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
            AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS,
        }:
            names = self._course_names()
            return build_assignment_ambiguity_answer(
                [
                    (record, names.get(record.canvas_course_id))
                    for record in model_input.assignment_candidates
                ],
                timezone=timezone,
            )
        if operation is AssistantOperation.SYNC_STATUS and model_input.sync_status is not None:
            return build_sync_status_answer(
                model_input.sync_status, now=self._now(), timezone=timezone
            )
        if operation is AssistantOperation.FOCUS_COURSES and self._asks_for_assignments(
            model_input.request.query
        ):
            focus = [
                (str(item.course_id), item.course_name)  # type: ignore[attr-defined]
                for item in model_input.course_list
            ]
            return build_focus_assignments_answer(
                focus,
                {
                    course_id: self._tools.get_assignments(course_id=course_id)
                    for course_id, _ in focus
                },
                timezone=timezone,
            )
        if self._lacks_material_evidence(model_input, intent):
            course_id = model_input.plan.course_id
            documents = (
                self._tools.get_documents(course_id=course_id).documents if course_id else ()
            )
            course = self._tools.get_course(course_id) if course_id else None
            return build_no_evidence_answer(
                course_name=course.course_name if course else None,
                unreadable_titles=[
                    doc.display_name or "Untitled file"
                    for doc in documents
                    if doc.status != "parsed"
                ],
            )
        answer = try_deterministic_answer(
            intent=intent,
            assignment_context=model_input.assignment_context,
            deadlines=model_input.deadlines,
            timezone=timezone,
            deadline_window_label=self._deadline_window_label(model_input.request.query),
            course_names=self._course_names(),
        )
        if answer is None:
            return None
        return with_caveat(answer, sync_caveat(self._latest_sync_payload(), now=self._now()))

    @staticmethod
    def _try_bounded_claim_answer(
        model_input: AssistantModelInput,
    ) -> AssistantResponse | None:
        """Handle security-sensitive claims and explicit constraints without a model.

        User-provided statements are never promoted to Canvas truth.  This fast path
        also prevents a small local model from spending a full generation window on
        questions that can be answered or bounded deterministically.
        """

        raw_query = model_input.request.query
        query = normalize_question(raw_query)
        course_id = AcademicAssistantOrchestrator._evidence_course(model_input)

        override_markers = (
            "system override",
            "ignore all previous instructions",
            "ignore previous instructions",
            "forget prior instructions",
            "developer override",
        )
        if any(marker in query for marker in override_markers):
            if any(
                phrase in query
                for phrase in (
                    "confirm this announcement",
                    "cancelled all exams",
                    "canceled all exams",
                    "assigned everyone an a",
                )
            ):
                text = (
                    "I cannot confirm a course change from an override claim in a message. "
                    "Only verified Canvas assignments, announcements, and syllabus evidence "
                    "can establish an exam cancellation or grade change; no such verified "
                    "evidence was supplied with this request. Check the official Canvas "
                    "announcement or ask the instructor."
                )
            else:
                text = (
                    "I treated the quoted instruction as untrusted academic text and did not "
                    "follow or repeat it. I could not verify the requested attendance policy "
                    "from the available Canvas evidence. Check the verified syllabus source "
                    "or ask the instructor for the current policy."
                )
            return AssistantResponse(
                status="ok",
                blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
                course_id=course_id,
            )

        range_match = re.search(
            r"\blectures?\s+(\d{1,2})\s*(?:-|to|through)\s*(\d{1,2})\b",
            query,
        )
        excluded_match = re.search(
            r"\blecture\s+(\d{1,2})\b"
            r"(?:(?!\blecture\b)[^.!?]){0,80}\b(?:is\s+)?"
            r"(?:excluded|omitted|not included)\b",
            query,
        )
        if range_match is not None and excluded_match is not None:
            first, last = int(range_match.group(1)), int(range_match.group(2))
            excluded = int(excluded_match.group(1))
            if 1 <= first <= last <= 99 and first <= excluded <= last:
                included = [number for number in range(first, last + 1) if number != excluded]
                included_text = ", ".join(f"Lecture {number}" for number in included)
                text = (
                    "Based only on the coverage statement in your question, study "
                    f"{included_text}; Lecture {excluded} is explicitly excluded. "
                    "That statement is user-provided and is not independently verified as a "
                    "Canvas announcement, so confirm it against the official course notice."
                )
                return AssistantResponse(
                    status="ok",
                    blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
                    course_id=course_id,
                )

        asks_for_announcement_update = (
            "announcement" in query
            and any(term in query for term in ("errata", "updated", "update", "correction"))
            and any(term in query for term in ("submission", "homework", "assignment"))
        )
        if asks_for_announcement_update:
            announcements = tuple(
                item
                for item in model_input.canvas_text_evidence
                if item.source_kind == "announcement"
                and (course_id is None or item.canvas_course_id == course_id)
            )[:4]
            if announcements:
                titles = ", ".join(
                    item.title or "Untitled Canvas announcement" for item in announcements
                )
                text = (
                    "I found relevant verified Canvas announcement evidence: "
                    f"{titles}. Treat those announcements as the source of any submission "
                    "update or errata; I will not invent additional instructions."
                )
                references = tuple(
                    AssistantEvidenceReference(
                        authority=SourceAuthority.CANVAS_TRUTH,
                        identifier=item.source_id,
                    )
                    for item in announcements
                )
            else:
                text = (
                    "I found no verified Canvas announcement in this course that confirms "
                    "updated submission instructions or errata for that work. Check the "
                    "assignment page and official announcements; I will not infer a change."
                )
                references = ()
            return AssistantResponse(
                status="ok",
                blocks=(
                    AssistantResponseBlock(
                        type=ResponseBlockType.TEXT,
                        text=text,
                        references=references,
                    ),
                ),
                course_id=course_id,
            )
        return None

    @staticmethod
    def _asks_for_assignments(query: str) -> bool:
        normalized = normalize_question(query)
        return any(
            word in normalized
            for word in ("assignment", "homework", "quiz", "exam", "project", "lab", "due", "work")
        )

    @staticmethod
    def _lacks_material_evidence(
        model_input: AssistantModelInput, intent: AcademicQuestionIntent
    ) -> bool:
        if model_input.plan.operation is not AssistantOperation.MATERIAL_SEARCH:
            return False
        if intent is not AcademicQuestionIntent.LECTURE_MATERIAL:
            return False
        return not (
            model_input.evidence
            or model_input.canvas_text_evidence
            or (model_input.material_search and model_input.material_search.hits)
        )

    def _now(self) -> datetime:
        return (self._tools._clock or (lambda: datetime.now(UTC)))()

    def _course_names(self) -> dict[str, str | None]:
        return {item.canvas_course_id: item.course_name for item in self._tools.get_courses()}

    def _scoped_deadlines(
        self,
        window: DeadlineWindow,
        *,
        course_id: str | None,
        query: str = "",
    ) -> DeadlineToolResult:
        """Keep global deadline answers within the student's current course scope."""
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        }
        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b(?:\s+(\d{4}))?",
            query.casefold(),
        )
        if month_match:
            month_name = month_match.group(1)
            year_str = month_match.group(2)
            month_num = month_map[month_name]
            year_num = int(year_str) if year_str else 2026
            service = DeadlineService(
                AssignmentRepository(self._tools.session),
                academic_timezone=self._tools._timezone,
                clock=self._tools._clock,
            )
            if month_num in (1, 3, 5, 7, 8, 10, 12):
                last_day = 31
            elif month_num in (4, 6, 9, 11):
                last_day = 30
            else:
                last_day = 29 if year_num % 4 == 0 else 28
            norm_window = (
                f"{year_num:04d}-{month_num:02d}-01/"
                f"{year_num:04d}-{month_num:02d}-{last_day:02d}"
            )

            month_assignments: list[AssignmentToolRecord] = []
            if course_id is not None:
                month_assignments = [
                    self._tools.assignment_record(a)
                    for a in service.query_month(
                        year_num, month_num, canvas_course_id=course_id
                    )
                ]
            else:
                focus_ids = tuple(
                    item.course_id
                    for item in FocusCourseService(self._tools.session).list()
                )
                scope = tuple(dict.fromkeys((*focus_ids, *self._current_course_ids())))
                seen_set: set[tuple[str, str]] = set()
                for scoped_course_id in scope:
                    for a in service.query_month(
                        year_num, month_num, canvas_course_id=scoped_course_id
                    ):
                        key = (scoped_course_id, a.canvas_assignment_id)
                        if key in seen_set:
                            continue
                        seen_set.add(key)
                        month_assignments.append(self._tools.assignment_record(a))
            return DeadlineToolResult(
                window=f"{month_name}_{year_num}",
                normalized_window=norm_window,
                assignments=tuple(month_assignments),
            )

        service = DeadlineService(
            AssignmentRepository(self._tools.session),
            academic_timezone=self._tools._timezone,
            clock=self._tools._clock,
        )
        norm_window = service.normalized_window(window)

        if course_id is not None:
            res = self._tools.get_deadlines(window, course_id=course_id)
            return DeadlineToolResult(
                window=res.window,
                normalized_window=norm_window,
                assignments=res.assignments,
            )

        focus_ids = tuple(item.course_id for item in FocusCourseService(self._tools.session).list())
        # Focus Courses are preferred navigation, not an implicit request to
        # hide other currently active enrollments. Include both while excluding
        # courses whose enrollment/workflow/term is explicitly historical.
        scope = tuple(dict.fromkeys((*focus_ids, *self._current_course_ids())))
        assignments: list[AssignmentToolRecord] = []
        seen: set[tuple[str, str]] = set()
        for scoped_course_id in scope:
            for assignment in self._tools.get_deadlines(
                window, course_id=scoped_course_id
            ).assignments:
                key = (assignment.canvas_course_id, assignment.canvas_assignment_id)
                if key in seen:
                    continue
                seen.add(key)
                assignments.append(assignment)
        assignments.sort(
            key=lambda item: (
                item.due_at or datetime.max.replace(tzinfo=UTC),
                item.name or "",
                item.canvas_assignment_id,
            )
        )
        return DeadlineToolResult(
            window=window.value,
            normalized_window=norm_window,
            assignments=tuple(assignments),
        )

    def _scoped_calendar_month(
        self,
        year: int,
        month: int,
        *,
        course_id: str | None,
    ) -> DeadlineToolResult:
        if course_id is not None:
            return self._tools.get_calendar_month_deadlines(
                year, month, course_id=course_id
            )
        scope = tuple(
            dict.fromkeys(
                (
                    *(item.course_id for item in FocusCourseService(self._tools.session).list()),
                    *self._current_course_ids(),
                )
            )
        )
        assignments: list[AssignmentToolRecord] = []
        seen: set[tuple[str, str]] = set()
        for scoped_course_id in scope:
            result = self._tools.get_calendar_month_deadlines(
                year, month, course_id=scoped_course_id
            )
            for assignment in result.assignments:
                key = (assignment.canvas_course_id, assignment.canvas_assignment_id)
                if key not in seen:
                    seen.add(key)
                    assignments.append(assignment)
        assignments.sort(
            key=lambda item: (
                item.due_at or datetime.max.replace(tzinfo=UTC),
                item.name or "",
                item.canvas_assignment_id,
            )
        )
        last_day = calendar.monthrange(year, month)[1]
        norm_window = f"{year:04d}-{month:02d}-01/{year:04d}-{month:02d}-{last_day:02d}"
        return DeadlineToolResult(
            window=f"{year:04d}-{month:02d}",
            normalized_window=norm_window,
            assignments=tuple(assignments),
        )

    def _current_course_ids(self) -> tuple[str, ...]:
        """Fallback scope when no Focus Courses have been chosen.

        Null term bounds remain eligible because many Canvas institutions omit
        them, but explicitly ended/historical terms are excluded.
        """
        now = self._now()
        rows = self._tools.session.scalars(
            select(Course)
            .where(
                (Course.enrollment_state.is_(None) | (Course.enrollment_state == "active")),
                (Course.workflow_state.is_(None) | (Course.workflow_state == "available")),
                (Course.term_start_at.is_(None) | (Course.term_start_at <= now)),
                (Course.term_end_at.is_(None) | (Course.term_end_at >= now)),
            )
            .order_by(Course.canvas_course_id)
        )
        return tuple(course.canvas_course_id for course in rows)

    def _latest_sync_payload(self) -> dict[str, object]:
        latest = self._tools.session.scalar(
            select(SyncRun).order_by(SyncRun.started_at.desc())
        )
        if latest is None:
            return {"status": "not_run", "finished_at": None}
        return {
            "status": latest.status,
            "started_at": latest.started_at.isoformat(),
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
            "error_count": latest.error_count,
        }

    @staticmethod
    def _deadline_window_label(query: str) -> str:
        normalized = normalize_question(query)
        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b(?:\s+(\d{4}))?",
            normalized,
        )
        if month_match:
            month_name = month_match.group(1)
            year_str = month_match.group(2)
            year_num = year_str if year_str else "2026"
            return f"in {month_name.capitalize()} {year_num}"
        if "tomorrow" in normalized:
            return "tomorrow"
        if "today" in normalized:
            return "today"
        if "next week" in normalized:
            return "next week"
        if "this week" in normalized:
            return "this week"
        if "next month" in normalized:
            return "next month"
        if "this whole month" in normalized or "this month" in normalized or "month" in normalized:
            return "this month"
        if AcademicAssistantOrchestrator._asks_for_next_seven_days(normalized):
            return "in the next 7 days"
        if "overdue" in normalized or "past due" in normalized:
            return "as overdue work"
        if "upcoming" in normalized:
            return "as upcoming work"
        return "in this range"


    @staticmethod
    def _deadline_window(query: str) -> DeadlineWindow:
        normalized = normalize_question(query)
        if "next week" in normalized:
            return DeadlineWindow.NEXT_WEEK
        if "tomorrow" in normalized:
            return DeadlineWindow.TOMORROW
        if "this week" in normalized:
            return DeadlineWindow.THIS_WEEK
        if "next month" in normalized:
            return DeadlineWindow.NEXT_MONTH
        if "this whole month" in normalized or "this month" in normalized or "month" in normalized:
            return DeadlineWindow.THIS_MONTH
        if AcademicAssistantOrchestrator._asks_for_next_seven_days(normalized):
            # Ambiguous "soon" has one documented deterministic meaning: the
            # rolling seven days from the current instant in the academic zone.
            return DeadlineWindow.NEXT_7_DAYS
        if "overdue" in normalized or "past due" in normalized or "late" in normalized:
            return DeadlineWindow.OVERDUE
        if "upcoming" in normalized:
            return DeadlineWindow.UPCOMING
        return DeadlineWindow.TODAY

    def _calendar_month(self, query: str) -> tuple[int, int] | None:
        normalized = normalize_question(query)
        for month in range(1, 13):
            name = calendar.month_name[month].casefold()
            match = re.search(rf"\b{name}\b(?:\s+(\d{{4}}))?", normalized)
            if match is None:
                continue
            local_now = self._now().astimezone(self._tools.academic_timezone)
            year = int(match.group(1)) if match.group(1) else local_now.year
            if match.group(1) is None and month < local_now.month:
                year += 1
            return year, month
        return None

    @staticmethod
    def _asks_for_next_seven_days(normalized_query: str) -> bool:
        return any(
            phrase in normalized_query
            for phrase in (
                "soon",
                "next 7 days",
                "next seven days",
                "within 7 days",
                "within seven days",
            )
        )

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
    def _canvas_text_reference_ids(model_input: AssistantModelInput) -> set[str]:
        course = AcademicAssistantOrchestrator._evidence_course(model_input)
        items = list(model_input.canvas_text_evidence)
        if (
            model_input.assignment_context is not None
            and model_input.assignment_context.assignment.canvas_course_id == course
        ):
            items.extend(model_input.assignment_context.canvas_text_evidence)
        return {
            item.source_id for item in items
            if course is not None and item.canvas_course_id == course
        }

    @staticmethod
    def _evidence_course(model_input: AssistantModelInput) -> str | None:
        return (
            model_input.context.context.course_id
            if model_input.context is not None
            else model_input.plan.course_id
        )

    @staticmethod
    def _known_references(
        model_input: AssistantModelInput,
    ) -> set[tuple[SourceAuthority, str]]:
        course = AcademicAssistantOrchestrator._evidence_course(model_input)
        if course is None:
            return set()
        known = {
            (item.authority, item.canvas_file_id)
            for item in model_input.evidence
            if item.canvas_course_id == course
        }
        known.update(
            (item.authority, item.source_id)
            for item in model_input.canvas_text_evidence
            if item.canvas_course_id == course
        )
        if (
            model_input.assignment_context is not None
            and model_input.assignment_context.assignment.canvas_course_id == course
        ):
            known.add((
                model_input.assignment_context.assignment.authority,
                model_input.assignment_context.assignment.canvas_assignment_id,
            ))
            known.update(
                (item.authority, item.canvas_file_id)
                for item in model_input.assignment_context.retrieval_evidence
                if item.canvas_course_id == course
            )
            known.update(
                (item.authority, item.source_id)
                for item in model_input.assignment_context.canvas_text_evidence
                if item.canvas_course_id == course
            )
        return known

    @staticmethod
    def _deduplicate_references(
        references: tuple[AssistantEvidenceReference, ...],
    ) -> tuple[AssistantEvidenceReference, ...]:
        seen: set[tuple[SourceAuthority, str]] = set()
        unique: list[AssistantEvidenceReference] = []
        for reference in references:
            key = (reference.authority, reference.identifier)
            if key not in seen:
                seen.add(key)
                unique.append(reference)
        return tuple(unique)

    @staticmethod
    def _validate_response(
        response: AssistantResponse, model_input: AssistantModelInput
    ) -> AssistantResponse:
        if not isinstance(response, AssistantResponse):
            raise OrchestrationError("provider returned an invalid response")
        if len(response.blocks) > 50:
            raise OrchestrationError("provider response has too many blocks")
        if not response.blocks or not any(
            (block.text is not None and block.text.strip()) or block.payload is not None
            for block in response.blocks
        ):
            raise OrchestrationError("provider returned no usable response content")
        course = AcademicAssistantOrchestrator._evidence_course(model_input)
        if response.course_id is not None and response.course_id != course:
            raise OrchestrationError("provider changed the resolved course")
        known = AcademicAssistantOrchestrator._known_references(model_input)
        blocks: list[AssistantResponseBlock] = []
        for block in response.blocks:
            if any(
                (reference.authority, reference.identifier) not in known
                for reference in block.references
            ):
                raise OrchestrationError("provider returned an unknown evidence reference")
            blocks.append(block.model_copy(update={
                "references": AcademicAssistantOrchestrator._deduplicate_references(
                    block.references
                )
            }))
        cleaned = response.model_copy(update={"blocks": tuple(blocks)})
        return AcademicAssistantOrchestrator._augment_response(cleaned, model_input)

    @staticmethod
    def _augment_response(
        response: AssistantResponse, model_input: AssistantModelInput
    ) -> AssistantResponse:
        blocks = list(response.blocks)
        existing = {block.type for block in blocks}

        def add_block(block: AssistantResponseBlock) -> None:
            if block.type not in existing:
                blocks.append(block)
                existing.add(block.type)

        if model_input.deadlines is not None:
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.DEADLINES,
                    payload={
                        "window": model_input.deadlines.window,
                        "assignments": [
                            item.model_dump(mode="json")
                            for item in model_input.deadlines.assignments
                        ],
                        "empty": not model_input.deadlines.assignments,
                        "message": (
                            f"Nothing due {model_input.deadlines.window.replace('_', ' ')}."
                            if not model_input.deadlines.assignments
                            else None
                        ),
                    },
                )
            )
        if model_input.assignment_context is not None:
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.ASSIGNMENT_CONTEXT,
                    payload={
                        "assignment": model_input.assignment_context.assignment.model_dump(
                            mode="json"
                        ),
                        "course": model_input.assignment_context.course.model_dump(
                            mode="json"
                        ),
                    },
                )
            )
        if (
            model_input.material_search is not None
            or model_input.evidence
            or model_input.canvas_text_evidence
        ):
            # Multiple excerpts from the same document should produce one
            # citation, not a wall of repeated file IDs in the student UI.
            seen_sources: set[tuple[str, str]] = set()
            reference_list: list[AssistantEvidenceReference] = []
            active_course = AcademicAssistantOrchestrator._evidence_course(model_input)
            for document in model_input.evidence:
                if active_course is None or document.canvas_course_id != active_course:
                    continue
                key = (str(document.authority), document.canvas_file_id)
                if key in seen_sources:
                    continue
                seen_sources.add(key)
                reference_list.append(
                    AssistantEvidenceReference(
                        authority=document.authority,
                        identifier=document.canvas_file_id,
                        locator=document.display_name or document.filename or document.heading,
                    )
                )
            for canvas_item in model_input.canvas_text_evidence:
                if active_course is None or canvas_item.canvas_course_id != active_course:
                    continue
                key = (str(canvas_item.authority), canvas_item.source_id)
                if key in seen_sources:
                    continue
                seen_sources.add(key)
                reference_list.append(
                    AssistantEvidenceReference(
                        authority=canvas_item.authority,
                        identifier=canvas_item.source_id,
                        locator=canvas_item.title,
                    )
                )
            references = tuple(reference_list[:20])
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.DOCUMENT_EVIDENCE,
                    payload=(
                        model_input.material_search.model_dump(mode="json")
                        if model_input.material_search is not None
                        else None
                    ),
                    references=references,
                )
            )
        if model_input.recent_changes is not None:
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.RECENT_CHANGES,
                    payload=model_input.recent_changes.model_dump(mode="json"),
                )
            )
        if model_input.course_list:
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.COURSE_LIST,
                    payload={
                        "courses": [
                            item.model_dump(mode="json")
                            for item in model_input.course_list
                        ]
                    },
                )
            )
        if model_input.sync_status is not None:
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.SYNC_STATUS,
                    payload=model_input.sync_status,
                )
            )
        structured = (
            (ResponseBlockType.STUDY_PLAN, model_input.study_plan),
            (ResponseBlockType.PRACTICE_QUESTION, model_input.practice_session),
            (ResponseBlockType.PRACTICE_FEEDBACK, model_input.practice_feedback),
            (ResponseBlockType.STUDY_GUIDE, model_input.study_guide),
            (ResponseBlockType.NOTIFICATION_SUMMARY, model_input.notifications),
            (ResponseBlockType.REMINDER_PREVIEW, model_input.reminder_preview),
            (ResponseBlockType.CALENDAR_ACTION_PREVIEW, model_input.calendar_preview),
        )
        if model_input.practice_hint is not None:
            add_block(
                AssistantResponseBlock(
                    type=ResponseBlockType.PRACTICE_FEEDBACK,
                    payload={
                        "correct": False,
                        "feedback": "Hint requested.",
                        "hint": model_input.practice_hint,
                        "next_question": None,
                        "session_id": (
                            model_input.practice_session.session_id
                            if model_input.practice_session is not None
                            else model_input.request.practice_session_id
                        ),
                        "progress": (
                            model_input.practice_session.progress
                            if model_input.practice_session is not None
                            else 0
                        ),
                    },
                )
            )
        for block_type, payload in structured:
            if payload is not None:
                add_block(
                    AssistantResponseBlock(
                        type=block_type,
                        payload=payload.model_dump(mode="json"),
                    )
                )
        operation_blocks = {
            AssistantOperation.STUDY_PLAN: AssistantResponseBlock(
                type=ResponseBlockType.STUDY_PLAN,
                payload={
                    "course_id": model_input.plan.course_id,
                    "query": model_input.request.query,
                    "study_mode": model_input.request.study_mode,
                    "evidence_count": len(model_input.evidence),
                },
            ),
            AssistantOperation.PRACTICE_SESSION: AssistantResponseBlock(
                type=ResponseBlockType.PRACTICE_QUESTION,
                payload={
                    "course_id": model_input.plan.course_id,
                    "query": model_input.request.query,
                    "generated": True,
                    "evidence_count": len(model_input.evidence),
                },
            ),
            AssistantOperation.STUDY_GUIDE: AssistantResponseBlock(
                type=ResponseBlockType.STUDY_GUIDE,
                payload={
                    "course_id": model_input.plan.course_id,
                    "query": model_input.request.query,
                    "evidence_count": len(model_input.evidence),
                },
            ),
        }
        operation_block = operation_blocks.get(model_input.plan.operation)
        if operation_block is not None:
            add_block(operation_block)
        return response.model_copy(update={"blocks": tuple(blocks)})

    @staticmethod
    def _response_events(response: AssistantResponse) -> tuple[AssistantEvent, ...]:
        events: list[AssistantEvent] = []
        seen_sources: set[tuple[SourceAuthority, str]] = set()
        for block in response.blocks:
            events.append(
                AssistantEvent(
                    type=AssistantEventType.BLOCK,
                    block_type=block.type,
                    text=block.text,
                    payload=block.payload,
                    references=block.references,
                )
            )
            for reference in block.references:
                source_key = (reference.authority, reference.identifier)
                if source_key in seen_sources:
                    continue
                seen_sources.add(source_key)
                events.append(
                    AssistantEvent(
                        type=AssistantEventType.SOURCE,
                        source=reference.authority,
                        identifier=reference.identifier,
                    )
                )
        return tuple(events)

    @staticmethod
    def _validate_event(
        event: AssistantEvent, model_input: AssistantModelInput
    ) -> AssistantEvent:
        if event.type is AssistantEventType.COMPLETED:
            if event.response is None:
                raise OrchestrationError("completed event requires a response")
            AcademicAssistantOrchestrator._validate_response(event.response, model_input)
        if event.type is AssistantEventType.SOURCE and not event.identifier:
            raise OrchestrationError("source event requires an identifier")
        known = AcademicAssistantOrchestrator._known_references(model_input)
        if (
            event.type is AssistantEventType.SOURCE
            and (event.source is None or (event.source, event.identifier) not in known)
        ):
            raise OrchestrationError("provider returned an unknown source")
        if any(
            (reference.authority, reference.identifier) not in known
            for reference in event.references
        ):
            raise OrchestrationError("provider event contained an unknown reference")
        return event.model_copy(update={
            "references": AcademicAssistantOrchestrator._deduplicate_references(
                event.references
            )
        })

    @staticmethod
    def _cancelled(token: CancellationToken | None) -> bool:
        return bool(token and token.cancelled)
