import type { AcademicApi } from "@/lib/api/academic-api";
import { AcademicApiNotFoundError } from "@/lib/api/errors";
import {
  MOCK_ASSIGNMENT_DETAILS,
  MOCK_ASSIGNMENTS,
  MOCK_CHANGES,
  MOCK_COURSES,
  MOCK_DOCUMENT_DETAILS,
  MOCK_MODULE_ITEMS,
  MOCK_MODULES,
  MOCK_NOTIFICATIONS,
  MOCK_SEARCH_RESULTS,
  MOCK_SYNC_RUNS,
} from "@/lib/api/mock/data";
import type { AssistantRequest, AssistantStreamEvent } from "@/lib/domain/assistant";
import type {
  AcademicContext,
  CourseProfile,
  CourseProfileData,
  CourseRoutingRequest,
  CourseRoutingResult,
  StudyContext,
} from "@/lib/domain/course-intelligence";
import type {
  AutomationPreviewRequest,
  CalendarConfirmation,
  ReminderPreference,
} from "@/lib/domain/planning";
import type {
  StudyGuideRequest,
  StudySessionCreateRequest,
} from "@/lib/domain/study-workflows";
import type {
  Assignment,
  AssignmentFilters,
  ChatMessage,
  DeadlinesGrouped,
  DocumentCoverageSummary,
  DocumentListParams,
  DocumentSearchParams,
  DocumentSummary,
  DocumentUnit,
} from "@/lib/domain/types";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

function filterAssignments(
  items: Assignment[],
  filters?: AssignmentFilters,
): Assignment[] {
  let out = [...items];
  if (filters?.courseId) {
    out = out.filter((a) => a.courseId === filters.courseId);
  }
  if (filters?.window) {
    out = out.filter((a) => a.deadlineWindow === filters.window);
  }
  return out.sort((a, b) => {
    if (!a.dueAt) return 1;
    if (!b.dueAt) return -1;
    return a.dueAt.localeCompare(b.dueAt);
  });
}

function nextImportant(assignments: Assignment[]): Assignment | null {
  const upcoming = assignments
    .filter((a) => a.deadlineWindow !== "past_due_time" && a.dueAt)
    .sort((a, b) => (a.dueAt ?? "").localeCompare(b.dueAt ?? ""));
  return upcoming[0] ?? null;
}

function addFollowUps(blocks: ChatMessage["blocks"]): ChatMessage["blocks"] {
  return blocks?.map((b) => {
    if (b.type === "deadlines") {
      return {
        ...b,
        followUps: [
          "Show everything due this week",
          "Open this course",
          "Help me study this topic",
        ],
      };
    }
    if (b.type === "document_answer") {
      return {
        ...b,
        followUps: ["Search the lecture notes", "Open source details"],
      };
    }
    return b;
  });
}

let mockStudySessionCounter = 0;
let mockPracticeSessionCounter = 0;
const mockStudySessions = new Map<string, import("@/lib/domain/study-workflows").StudySession>();
const mockPracticeSessions = new Map<
  string,
  import("@/lib/domain/study-workflows").PracticeSession
>();

export class MockAcademicApi implements AcademicApi {
  private notifications = [...MOCK_NOTIFICATIONS];
  private reminderPreferences = {
    enabled: true,
    leadTimesHours: [24, 3],
    timezone: "America/Chicago",
    courseOverrides: {} as Record<string, number[]>,
  };

  async getCourses() {
    await delay();
    return MOCK_COURSES;
  }

  async getCourse(courseId: string) {
    await delay();
    return MOCK_COURSES.find((c) => c.id === courseId) ?? null;
  }

  async getAssignments(filters?: AssignmentFilters) {
    await delay();
    return filterAssignments(MOCK_ASSIGNMENTS, filters);
  }

  async getAssignment(assignmentId: string) {
    await delay();
    const detail = MOCK_ASSIGNMENT_DETAILS[assignmentId];
    if (detail) return detail;
    const base = MOCK_ASSIGNMENTS.find((a) => a.id === assignmentId);
    if (!base) return null;
    return {
      ...base,
      descriptionPlainText: "No extended description in mock data (sample).",
    };
  }

  async getDeadlines(): Promise<DeadlinesGrouped> {
    await delay();
    return {
      today: filterAssignments(MOCK_ASSIGNMENTS, { window: "today" }),
      tomorrow: filterAssignments(MOCK_ASSIGNMENTS, { window: "tomorrow" }),
      thisWeek: filterAssignments(MOCK_ASSIGNMENTS, { window: "this_week" }),
    };
  }

  async getDashboard() {
    await delay(150);
    const deadlines = await this.getDeadlines();
    const all = await this.getAssignments();
    return {
      nextDeadline: nextImportant(all),
      dueToday: deadlines.today,
      dueTomorrow: deadlines.tomorrow,
      thisWeek: deadlines.thisWeek,
      upcomingWorkload: all
        .filter((a) => a.deadlineWindow !== "past_due_time")
        .slice(0, 6),
      recentChanges: MOCK_CHANGES.slice(0, 4),
      suggestedMaterials: MOCK_SEARCH_RESULTS,
      lastSync: MOCK_SYNC_RUNS[0] ?? null,
    };
  }

  async getModules(courseId?: string) {
    await delay();
    if (!courseId) return MOCK_MODULES;
    return MOCK_MODULES.filter((m) => m.courseId === courseId);
  }

  async getModuleItems(courseId: string) {
    await delay();
    return MOCK_MODULE_ITEMS.filter((m) => m.courseId === courseId);
  }

  async getChanges(limit = 50) {
    await delay();
    return MOCK_CHANGES.slice(0, limit);
  }

  async getSyncRuns(limit = 20) {
    await delay();
    return MOCK_SYNC_RUNS.slice(0, limit);
  }

  async getSyncRun(runId: number) {
    await delay();
    return MOCK_SYNC_RUNS.find((r) => r.id === runId) ?? null;
  }

  async getLatestSyncRun() {
    await delay();
    return MOCK_SYNC_RUNS[0] ?? null;
  }

  async probeCanvasConnection(): Promise<
    "ready" | "not_configured" | "unavailable"
  > {
    await delay(40);
    return "ready";
  }

  async triggerCanvasSync() {
    await delay(80);
    return { accepted: true, message: "Mock sync started." };
  }

  async getNotifications() {
    await delay(80);
    return this.notifications.filter((n) => !n.dismissed);
  }

  async markNotificationRead(notificationId: string) {
    await delay(40);
    const item = this.notifications.find((n) => n.id === notificationId);
    if (!item) throw new Error("notification not found");
    item.read = true;
    return { ...item };
  }

  async dismissNotification(notificationId: string) {
    await delay(40);
    const item = this.notifications.find((n) => n.id === notificationId);
    if (!item) throw new Error("notification not found");
    item.dismissed = true;
    item.read = true;
    return { ...item };
  }

  async getReminderPreferences() {
    await delay(60);
    return { ...this.reminderPreferences, courseOverrides: { ...this.reminderPreferences.courseOverrides } };
  }

  async saveReminderPreferences(preference: ReminderPreference) {
    await delay(80);
    this.reminderPreferences = {
      ...preference,
      courseOverrides: { ...preference.courseOverrides },
    };
    return this.getReminderPreferences();
  }

  async previewReminderPlan(courseId: string, assignmentId: string) {
    await delay(80);
    const assignment = MOCK_ASSIGNMENTS.find((a) => a.id === assignmentId && a.courseId === courseId);
    const dueAt = assignment?.dueAt ?? new Date().toISOString();
    const leads = this.reminderPreferences.leadTimesHours;
    return {
      title: "Reminder plan preview (mock)",
      summary: `${leads.length} reminder(s) before the due date.`,
      plan: {
        planId: `mock:${courseId}:${assignmentId}`,
        courseId,
        assignmentId,
        dueAt,
        enabled: this.reminderPreferences.enabled,
        reminders: leads.map((h) => ({
          at: dueAt,
          leadHours: h,
          status: "scheduled" as const,
        })),
      },
    };
  }

  async listCalendarLinks() {
    await delay(40);
    return [
      {
        provider: "memory",
        calendarId: "mock-primary",
        displayName: "Mock academic calendar",
        enabled: true,
      },
    ];
  }

  async linkCalendar(link: { provider: string; calendarId: string; displayName: string }) {
    await delay(60);
    return { ...link, enabled: true };
  }

  async previewCalendarEvent(courseId: string, assignmentId: string) {
    await delay(80);
    const assignment = MOCK_ASSIGNMENTS.find((a) => a.id === assignmentId);
    const start = assignment?.dueAt ?? new Date().toISOString();
    return {
      event: {
        eventId: `preview:${assignmentId}`,
        courseId,
        assignmentId,
        summary: assignment?.title ?? "Assignment",
        description: "Mock calendar preview — confirm to simulate a local write.",
        startAt: start,
        endAt: start,
        allDay: false,
        status: "pending" as const,
        source: "canvas",
        externalId: null,
        provider: "memory",
      },
      confirmation: {
        actionId: `action-mock-${assignmentId}`,
        confirmationToken: "mock-token",
      },
    };
  }

  async confirmCalendarEvent(confirmation: CalendarConfirmation) {
    await delay(100);
    if (confirmation.confirmationToken === "used") {
      const err = new Error("confirmation already used");
      throw err;
    }
    return {
      actionId: confirmation.actionId,
      status: "confirmed" as const,
      event: {
        eventId: `memory:${confirmation.actionId}`,
        courseId: "mock",
        assignmentId: null,
        summary: "Confirmed (mock)",
        description: null,
        startAt: new Date().toISOString(),
        endAt: new Date().toISOString(),
        allDay: false,
        status: "confirmed" as const,
        source: "canvas",
        externalId: "memory:1",
        provider: "memory",
      },
      message: "Calendar action executed (mock provider).",
    };
  }

  async previewAutomation(request: AutomationPreviewRequest) {
    await delay(60);
    if (request.operation === "list_notifications") {
      const list = await this.getNotifications();
      return {
        operation: request.operation,
        title: "Academic notifications",
        summary: `${list.length} notification(s) are available.`,
        payload: { total: list.length },
        requiresConfirmation: false,
        safeToExecute: true,
      };
    }
    return {
      operation: request.operation,
      title: "Automation preview (mock)",
      summary: "Preview only in mock mode.",
      payload: null,
      requiresConfirmation: request.operation === "preview_calendar_event",
      safeToExecute: request.operation !== "preview_calendar_event",
    };
  }

  async createStudySession(request: StudySessionCreateRequest) {
    await delay(80);
    mockStudySessionCounter += 1;
    const sessionId = `mock-study-${mockStudySessionCounter}`;
    const steps = [
      { order: 1, title: "Orient", minutes: 10, status: "pending" },
      { order: 2, title: "Practice", minutes: 20, status: "pending" },
      { order: 3, title: "Review", minutes: 15, status: "pending" },
    ];
    const session = {
      sessionId,
      courseId: request.courseId,
      goal: request.goal,
      durationMinutes: request.durationMinutes,
      topics: request.topics,
      studyMode: request.studyMode,
      assignmentIds: request.assignmentIds,
      status: "active" as const,
      relevantEvidence: [],
      steps,
      progress: 0,
    };
    mockStudySessions.set(sessionId, session);
    return session;
  }

  async getStudySession(sessionId: string) {
    await delay(40);
    const session = mockStudySessions.get(sessionId);
    if (!session) throw new AcademicApiNotFoundError("Study session");
    return session;
  }

  async continueStudySession(sessionId: string) {
    const session = await this.getStudySession(sessionId);
    if (session.status === "completed") throw new Error("completed study session cannot be continued");
    const next = { ...session, status: "active" as const };
    mockStudySessions.set(sessionId, next);
    return next;
  }

  async advanceStudySession(sessionId: string, completedStep: number) {
    const session = await this.getStudySession(sessionId);
    const steps = session.steps.map((s) => ({
      ...s,
      status: s.order <= completedStep ? "complete" : "pending",
    }));
    const progress = Math.round((completedStep / steps.length) * 100);
    const next = {
      ...session,
      steps,
      progress,
      status: (progress >= 100 ? "completed" : "active") as "active" | "completed",
    };
    mockStudySessions.set(sessionId, next);
    return next;
  }

  async createPracticeSession(courseId: string, topic: string, totalQuestions = 5) {
    await delay(80);
    mockPracticeSessionCounter += 1;
    const sessionId = `mock-practice-${mockPracticeSessionCounter}`;
    const session = {
      sessionId,
      courseId,
      topic,
      status: "active",
      questionIndex: 0,
      totalQuestions,
      correctAnswers: 0,
      question: {
        question: `Explain one important idea about ${topic}.`,
        generated: true,
        evidence: [],
      },
      progress: 0,
    };
    mockPracticeSessions.set(sessionId, session);
    return session;
  }

  async getPracticeSession(sessionId: string) {
    await delay(40);
    const session = mockPracticeSessions.get(sessionId);
    if (!session) throw new Error("practice session not found");
    return session;
  }

  async answerPracticeSession(sessionId: string, answer: string) {
    await delay(80);
    const session = await this.getPracticeSession(sessionId);
    const correct = answer.trim().length >= 20;
    const nextIndex = session.questionIndex + 1;
    const done = nextIndex >= session.totalQuestions;
    return {
      correct,
      feedback: correct ? "Good substantive answer (mock)." : "Add more detail (mock).",
      hint: correct ? null : "Define the concept first.",
      nextQuestion: done
        ? null
        : {
            question: `Follow-up on ${session.topic}?`,
            generated: true,
            evidence: [],
          },
      progress: Math.round((nextIndex / session.totalQuestions) * 100),
    };
  }

  async hintPracticeSession(sessionId: string) {
    void sessionId;
    await delay(40);
    return "Start with a definition, then give an example (mock hint).";
  }

  async buildStudyGuide(request: StudyGuideRequest) {
    await delay(100);
    return {
      title: `Study guide: ${request.topic ?? "course review"} (mock)`,
      scope: `Course ${request.courseId}`,
      keyConcepts: ["Core idea 1", "Core idea 2"],
      explanations: ["Explanation grounded in local fixtures when HTTP mode is on."],
      evidence: [],
      reviewChecklist: ["Skim notes", "Attempt practice questions"],
      practicePrompts: ["Summarize the topic in your own words."],
      uncertainties: ["Verify due dates in Canvas."],
    };
  }

  async listDocuments(params?: DocumentListParams): Promise<DocumentSummary[]> {
    await delay(120);
    const results = await this.searchDocuments({
      query: "",
      courseId: params?.courseId,
      documentType: params?.documentType,
    });
    return results.map((r) => ({
      documentId: r.documentId,
      title: r.title,
      courseId: r.courseId,
      courseName: r.courseName,
      documentType: r.documentType,
      ingestionState: "searchable",
      isStale: Boolean(r.isStale),
      needsOcr: false,
      unitCount: 1,
      backendStatus: "parsed",
    }));
  }

  async searchDocuments(params: DocumentSearchParams) {
    await delay(180);
    const q = params.query.trim().toLowerCase();
    let results = MOCK_SEARCH_RESULTS;
    if (params.courseId) {
      results = results.filter((r) => r.courseId === params.courseId);
    }
    if (params.documentType) {
      results = results.filter((r) => r.documentType === params.documentType);
    }
    if (!q) return results;
    return results.filter(
      (r) =>
        r.title.toLowerCase().includes(q) ||
        r.snippet.toLowerCase().includes(q) ||
        r.courseName.toLowerCase().includes(q),
    );
  }

  async getDocument(documentId: string) {
    await delay();
    return MOCK_DOCUMENT_DETAILS[documentId] ?? null;
  }

  async getDocumentUnits(documentId: string): Promise<DocumentUnit[]> {
    const doc = await this.getDocument(documentId);
    return doc?.units ?? [];
  }

  async getDocumentCoverage(courseId: string): Promise<DocumentCoverageSummary> {
    await delay(30);
    const docs = await this.listDocuments({ courseId });
    return {
      canvas_course_id: courseId,
      known_files: docs.length,
      eligible_files: docs.length,
      indexed_current: docs.filter((d) => d.ingestionState === "indexed").length,
      indexed_stale: docs.filter((d) => d.isStale).length,
      awaiting_download: docs.filter((d) => d.ingestionState === "pending").length,
      needs_ocr: docs.filter((d) => d.needsOcr).length,
      unsupported: 0,
      failed: docs.filter((d) => d.ingestionState === "failed").length,
    };
  }

  async listCourseProfiles(): Promise<CourseProfile[]> {
    await delay(80);
    return [await this.getCourseProfile("course-robots")].filter(Boolean) as CourseProfile[];
  }

  async getCourseProfile(courseId: string): Promise<CourseProfile | null> {
    await delay(80);
    const course = MOCK_COURSES.find((c) => c.id === courseId);
    if (!course) return null;
    return {
      courseId: course.id,
      courseName: course.name,
      courseCode: course.code ?? null,
      hasCustomProfile: courseId === "course-robots",
      profile: null,
      effectivePreferences: {
        teachingDepth: "balanced",
        startingLevel: "course_context",
        explanationStyle: "step_by_step",
        answerStyle: "balanced",
        stepByStep: true,
        examStyle: false,
        visualPreference: "auto",
        mathDetail: "auto",
        codeDetail: "auto",
      },
      effectiveCourseInstructions: "Focus on kinematics intuition before algebra.",
      updatedAt: null,
    };
  }

  async updateCourseProfile(
    courseId: string,
    update: Partial<CourseProfileData>,
  ): Promise<CourseProfile> {
    const existing = await this.getCourseProfile(courseId);
    if (!existing) throw new Error("Course not found");
    return {
      ...existing,
      hasCustomProfile: true,
      effectivePreferences: { ...existing.effectivePreferences, ...update },
      effectiveCourseInstructions:
        update.studyInstructions ?? existing.effectiveCourseInstructions,
    };
  }

  async getStudyContext(courseId: string): Promise<StudyContext | null> {
    const course = MOCK_COURSES.find((c) => c.id === courseId);
    if (!course) return null;
    return {
      courseId,
      courseName: course.name,
      hasContext: false,
      currentTopic: null,
      assignmentId: null,
      studyMode: "balanced",
      startingPoint: null,
      conceptsCovered: [],
      topicsToRevisit: [],
      studyNote: null,
      updatedAt: null,
    };
  }

  async updateStudyContext(
    courseId: string,
    update: Partial<StudyContext>,
  ): Promise<StudyContext> {
    const base = await this.getStudyContext(courseId);
    if (!base) throw new Error("Course not found");
    return { ...base, ...update, hasContext: true };
  }

  async resolveCourseRouter(request: CourseRoutingRequest): Promise<CourseRoutingResult> {
    await delay(60);
    const courseId =
      request.courseId ??
      request.activeCourseId ??
      (request.assignmentId ? MOCK_ASSIGNMENTS.find((a) => a.id === request.assignmentId)?.courseId : undefined);
    if (!courseId) {
      return {
        outcome: "unresolved",
        course: null,
        evidence: [],
        candidates: [],
        reason: "No course signal in mock router.",
      };
    }
    const course = MOCK_COURSES.find((c) => c.id === courseId);
    return {
      outcome: "resolved",
      course: course
        ? { courseId: course.id, courseName: course.name, courseCode: course.code ?? null }
        : null,
      evidence: ["explicit_course"],
      candidates: [],
      reason: "Resolved from explicit mock context.",
    };
  }

  async resolveAcademicContext(
    request: CourseRoutingRequest,
  ): Promise<AcademicContext | null> {
    const routing = await this.resolveCourseRouter(request);
    if (!routing.course) return null;
    const profile = await this.getCourseProfile(routing.course.courseId);
    const study = await this.getStudyContext(routing.course.courseId);
    if (!profile || !study) return null;
    return {
      courseId: routing.course.courseId,
      courseName: routing.course.courseName,
      courseCode: routing.course.courseCode,
      routingEvidence: routing.evidence,
      profilePreferences: profile.effectivePreferences,
      courseInstructions: profile.effectiveCourseInstructions,
      studyContext: study,
    };
  }

  async askAssistant(prompt: string, courseId?: string): Promise<ChatMessage> {
    return this.askAssistantAdvanced({ prompt, courseId });
  }

  async askAssistantAdvanced(request: AssistantRequest): Promise<ChatMessage> {
    const events: AssistantStreamEvent[] = [];
    for await (const ev of this.streamAssistant(request)) {
      events.push(ev);
    }
    const done = events.find((e) => e.type === "done");
    if (done && done.type === "done") return done.message;
    throw new Error("Assistant stream incomplete");
  }

  async *streamAssistant(request: AssistantRequest): AsyncIterable<AssistantStreamEvent> {
    yield { type: "status", status: "thinking" };
    await delay(300);
    const { prompt, courseId } = request;
    const lower = prompt.toLowerCase();
    const id = `asst-${Date.now()}`;

    let message: ChatMessage;

    if (lower.includes("quiz 3") && lower.includes("prepare")) {
      const course = MOCK_COURSES.find((c) => c.id === (courseId ?? "course-robots"));
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          { type: "course", content: "Synthetic course context:", course },
          {
            type: "text",
            content:
              "Quiz 3 preparation plan (demo): review the motion-planning module, trace one A* grid example by hand, then practice distinguishing forward and inverse kinematics. This plan is grounded only in the synthetic sample sources below.",
          },
          {
            type: "document_answer",
            content:
              "The sample lecture source covers motion planning and the sample homework source covers kinematics practice. No real professor or student content is used.",
            sources: MOCK_SEARCH_RESULTS.slice(0, 2).map((result, index) => ({
              id: `src-quiz-plan-${index}`,
              provenance: result.provenance,
            })),
          },
        ]),
      };
    } else if (lower.includes("assignment") || request.assignmentId) {
      const asgn = await this.getAssignment(request.assignmentId ?? "asgn-robots-quiz");
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          {
            type: "assignment_summary",
            content: "Sample assignment context (mock):",
            assignments: asgn ? [asgn] : [],
          },
          {
            type: "text",
            content: asgn?.descriptionPlainText?.slice(0, 200) ?? "No assignment data.",
          },
        ]),
      };
    } else if (lower.includes("due today") || lower.includes("what's due")) {
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          {
            type: "deadlines",
            content: "Sample deadlines for today (mock data):",
            assignments: filterAssignments(MOCK_ASSIGNMENTS, {
              window: "today",
              courseId,
            }),
          },
        ]),
      };
    } else if (lower.includes("week") || lower.includes("work on")) {
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          {
            type: "study",
            content: "Sample study plan for the week (mock):",
            studyTips: [
              "Block 90 minutes for Neural Networks homework (sample).",
              "Review Autonomous Robots lecture notes before the quiz (sample).",
            ],
            followUps: ["Show everything due this week"],
          },
        ]),
      };
    } else if (lower.includes("incomplete") || lower.includes("missing data")) {
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "incomplete_data",
        blocks: [
          {
            type: "warning",
            content:
              "Sample warning: some course materials are not indexed yet (mock incomplete state).",
          },
        ],
      };
    } else if (lower.includes("robot") || lower.includes("study")) {
      const course = MOCK_COURSES.find(
        (c) => c.id === (courseId ?? "course-robots"),
      );
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          { type: "course", content: "Course context (sample):", course },
          {
            type: "document_answer",
            content:
              "Sample answer — inverse kinematics overview (mock, not real professor content).",
            sources: MOCK_SEARCH_RESULTS.slice(0, 2).map((r, i) => ({
              id: `src-${i}`,
              provenance: r.provenance,
            })),
          },
        ]),
      };
    } else if (lower.includes("search") || lower.includes("material")) {
      const results = await this.searchDocuments({ query: "kinematics", courseId });
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          {
            type: "document_answer",
            content: `Found ${results.length} sample matches in mock materials.`,
            sources: results.map((r, i) => ({
              id: `src-search-${i}`,
              provenance: r.provenance,
            })),
          },
        ]),
      };
    } else if (lower.includes("changed") || lower.includes("sync")) {
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: addFollowUps([
          {
            type: "changes_summary",
            content: "Recent deterministic Canvas changes (mock):",
            changes: MOCK_CHANGES.slice(0, 3),
          },
        ]),
      };
    } else {
      message = {
        id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: [
          {
            type: "text",
            content:
              "Sample assistant reply (mock). Try prompts about due dates, materials, or course study.",
          },
        ],
      };
    }

    yield { type: "status", status: "streaming" };
    for (const block of message.blocks ?? []) {
      yield { type: "block", block };
      await delay(80);
    }
    yield { type: "done", message };
    yield { type: "status", status: "complete" };
  }
}
