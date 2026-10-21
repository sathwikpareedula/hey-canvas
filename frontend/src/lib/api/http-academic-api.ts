import {
  filterUpcomingAssignments,
  pickNextDeadline,
} from "@/lib/assignments/deadline-selection";
import type { AcademicApi } from "@/lib/api/academic-api";
import { AcademicApiError, AcademicApiNotImplementedError } from "@/lib/api/errors";
import {
  mapAssignment,
  mapChange,
  mapCourse,
  mapSyncRun,
  stripHtmlToPlain,
  type BackendAssignment,
  type BackendChange,
  type BackendCourse,
  type BackendSyncRun,
} from "@/lib/api/http/adapters";
import { mapDeadlineWindowToBackend } from "@/lib/api/http/contract-mappings";
import {
  mapAcademicContext,
  mapCourseProfile,
  mapCourseProfileUpdateToBackend,
  mapCourseRoutingRequestToBackend,
  mapCourseRoutingResult,
  mapStudyContext,
  mapStudyContextUpdateToBackend,
} from "@/lib/api/http/course-profile-adapters";
import {
  mapBackendDocumentTypeToQuery,
  mapDocumentDetail,
  mapDocumentSearchHit,
  mapDocumentSummary,
  mapDocumentSummaryToBrowseResult,
  mapUnitFromBackend,
  primaryCourseIdFromDocument,
  primaryCourseIdFromRefs,
  type BackendDocumentSearchHit,
  type BackendDocumentUnitView,
  type BackendDocumentView,
} from "@/lib/api/http/document-adapters";
import {
  mapAutomationRequestToBackend,
  mapBackendAutomationPreview,
} from "@/lib/api/http/automation-adapters";
import {
  mapBackendCalendarExecution,
  mapBackendCalendarLink,
  mapBackendCalendarPreview,
  mapCalendarConfirmationToBackend,
} from "@/lib/api/http/calendar-adapters";
import { fetchJson, postJson, putJson } from "@/lib/api/http/fetch-json";
import {
  mapBackendNotification,
  mapBackendNotificationList,
} from "@/lib/api/http/notification-adapters";
import {
  mapBackendReminderPreference,
  mapBackendReminderPreview,
  mapReminderPreferenceToBackend,
} from "@/lib/api/http/reminder-adapters";
import {
  mapBackendPracticeFeedback,
  mapBackendPracticeSession,
  mapBackendStudyGuide,
  mapBackendStudySession,
  mapPracticeCreateToBackend,
  mapStudyGuideRequestToBackend,
  mapStudySessionCreateToBackend,
} from "@/lib/api/http/study-workflow-adapters";
import { expectArray } from "@/lib/api/http/validate";

interface BackendModuleItem {
  canvas_module_item_id: string;
  canvas_module_id: string;
  canvas_course_id: string;
  title: string | null;
  item_type: string;
  position: number | null;
}

interface BackendModule {
  canvas_module_id: string;
  canvas_course_id: string;
  name: string | null;
  position: number | null;
  items: BackendModuleItem[];
}
import type { CourseProfileData, CourseRoutingRequest } from "@/lib/domain/course-intelligence";
import type { AssistantRequest, AssistantStreamEvent } from "@/lib/domain/assistant";
import type {
  AssignmentDetail,
  AssignmentFilters,
  ChatMessage,
  DashboardSnapshot,
  DeadlineWindow,
  DocumentCoverageSummary,
  DocumentListParams,
  DocumentSearchParams,
  SyncRun,
} from "@/lib/domain/types";

import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";

const baseUrl = () => resolveApiBaseUrl();

export class HttpAcademicApi implements AcademicApi {
  private courseNameById = new Map<string, string>();

  private courseName(courseId: string | undefined): string {
    if (!courseId) return "Unknown course";
    return this.courseNameById.get(courseId) ?? "Unknown course";
  }

  private async loadCourses() {
    const rows = expectArray<BackendCourse>(
      await fetchJson<unknown>(`${baseUrl()}/api/courses`),
      "courses",
    );
    const courses = rows.map(mapCourse);
    this.courseNameById = new Map(courses.map((c) => [c.id, c.name]));
    return courses;
  }

  async getCourses() {
    return this.loadCourses();
  }

  async getCourse(courseId: string) {
    const courses = await this.getCourses();
    return courses.find((c) => c.id === courseId) ?? null;
  }

  async getAssignments(filters?: AssignmentFilters) {
    if (filters?.window) {
      const backendWindow = mapDeadlineWindowToBackend(filters.window);
      const windowRows = expectArray<BackendAssignment>(
        await fetchJson<unknown>(
          `${baseUrl()}/api/deadlines?window=${backendWindow}${
            filters.courseId ? `&course_id=${encodeURIComponent(filters.courseId)}` : ""
          }`,
        ),
        "deadlines",
      );
      return windowRows.map((r) => mapAssignment(r, filters.window));
    }
    const params = new URLSearchParams();
    if (filters?.courseId) params.set("course_id", filters.courseId);
    const qs = params.toString();
    const rows = expectArray<BackendAssignment>(
      await fetchJson<unknown>(`${baseUrl()}/api/assignments${qs ? `?${qs}` : ""}`),
      "assignments",
    );
    return rows.map((r) => mapAssignment(r));
  }

  async getAssignment(assignmentId: string): Promise<AssignmentDetail | null> {
    const rows = expectArray<BackendAssignment>(
      await fetchJson<unknown>(`${baseUrl()}/api/assignments`),
      "assignments",
    );
    const row = rows.find((r) => r.canvas_assignment_id === assignmentId);
    if (!row) return null;
    const base = mapAssignment(row);
    return {
      ...base,
      descriptionPlainText: stripHtmlToPlain(row.description_html),
    };
  }

  async getDeadlines() {
    const windows: DeadlineWindow[] = ["today", "tomorrow", "this_week"];
    const [today, tomorrow, thisWeek] = await Promise.all(
      windows.map((w) =>
        fetchJson<unknown>(`${baseUrl()}/api/deadlines?window=${w}`).then((raw) =>
          expectArray<BackendAssignment>(raw, "deadlines").map((r) => mapAssignment(r, w)),
        ),
      ),
    );
    return { today, tomorrow, thisWeek };
  }

  async getDashboard(): Promise<DashboardSnapshot> {
    const [deadlines, assignments, changes] = await Promise.all([
      this.getDeadlines(),
      this.getAssignments(),
      this.getChanges(4),
    ]);
    let lastSync: SyncRun | null = null;
    try {
      lastSync = await this.getLatestSyncRun();
    } catch {
      lastSync = null;
    }
    let materials: import("@/lib/domain/types").DocumentSearchResult[] = [];
    try {
      const listed = await this.listDocuments({ limit: 6 });
      materials = listed.map(mapDocumentSummaryToBrowseResult);
    } catch (err) {
      if (!(err instanceof AcademicApiNotImplementedError)) throw err;
    }
    const upcoming = filterUpcomingAssignments(assignments, new Date(), 8);
    return {
      nextDeadline: pickNextDeadline(assignments),
      dueToday: deadlines.today,
      dueTomorrow: deadlines.tomorrow,
      thisWeek: deadlines.thisWeek,
      upcomingWorkload: upcoming.slice(0, 8),
      recentChanges: changes,
      suggestedMaterials: materials.slice(0, 3),
      lastSync,
    };
  }

  async getModules(courseId?: string): Promise<import("@/lib/domain/types").Module[]> {
    const query = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
    const rows = expectArray<BackendModule>(
      await fetchJson<unknown>(`${baseUrl()}/api/modules${query}`),
      "modules",
    );
    return rows.map((row) => ({
      id: row.canvas_module_id,
      courseId: row.canvas_course_id,
      name: row.name ?? "Untitled module",
      position: row.position ?? 0,
    }));
  }

  async getModuleItems(courseId: string): Promise<import("@/lib/domain/types").ModuleItem[]> {
    const rows = expectArray<BackendModule>(
      await fetchJson<unknown>(
        `${baseUrl()}/api/courses/${encodeURIComponent(courseId)}/modules`,
      ),
      "course modules",
    );
    return rows.flatMap((row) =>
      row.items.map((item) => ({
        id: item.canvas_module_item_id,
        moduleId: item.canvas_module_id,
        courseId: item.canvas_course_id,
        title: item.title ?? "Untitled module item",
        type: item.item_type,
        position: item.position ?? 0,
      })),
    );
  }

  async getChanges(limit = 50) {
    await this.loadCourses();
    const rows = expectArray<BackendChange>(
      await fetchJson<unknown>(`${baseUrl()}/api/changes?limit=${limit}`),
      "changes",
    );
    return rows.map((r) =>
      mapChange(
        r,
        r.course_canvas_id
          ? this.courseNameById.get(r.course_canvas_id)
          : undefined,
      ),
    );
  }

  async getSyncRuns(limit = 50) {
    const rows = expectArray<BackendSyncRun>(
      await fetchJson<unknown>(`${baseUrl()}/api/sync-runs?limit=${limit}`),
      "sync runs",
    );
    return rows.map(mapSyncRun);
  }

  async getSyncRun(runId: number) {
    try {
      const row = await fetchJson<BackendSyncRun>(`${baseUrl()}/api/sync-runs/${runId}`);
      return mapSyncRun(row);
    } catch (err) {
      if (err instanceof AcademicApiError && err.kind === "not_found") return null;
      throw err;
    }
  }

  async getLatestSyncRun() {
    const runs = await this.getSyncRuns(1);
    return runs[0] ?? null;
  }

  async probeCanvasConnection() {
    const row = await fetchJson<{ status: string }>(`${baseUrl()}/api/canvas/connection`);
    if (row.status === "ready") return "ready";
    if (row.status === "not_configured") return "not_configured";
    return "unavailable";
  }

  async triggerCanvasSync() {
    const { postJson } = await import("@/lib/api/http/fetch-json");
    const row = await postJson<{ accepted: boolean; message: string }>(
      `${baseUrl()}/api/canvas/sync`,
      {},
    );
    return { accepted: row.accepted, message: row.message };
  }

  async listDocuments(params?: DocumentListParams) {
    await this.loadCourses();
    const qs = new URLSearchParams();
    if (params?.courseId) qs.set("course_id", params.courseId);
    if (params?.status) qs.set("status", params.status);
    if (params?.documentType) {
      const dt = mapBackendDocumentTypeToQuery(params.documentType);
      if (dt) qs.set("document_type", dt);
    }
    if (params?.limit) qs.set("limit", String(params.limit));
    const rows = expectArray<BackendDocumentView>(
      await fetchJson<unknown>(`${baseUrl()}/api/documents${qs.toString() ? `?${qs}` : ""}`),
      "documents",
    );
    return rows.map((row) =>
      mapDocumentSummary(row, this.courseName(primaryCourseIdFromDocument(row))),
    );
  }

  async searchDocuments(params: DocumentSearchParams) {
    const q = params.query.trim();
    if (!q) {
      const listed = await this.listDocuments({
        courseId: params.courseId,
        documentType: params.documentType,
        limit: params.limit ?? 50,
      });
      return listed.map(mapDocumentSummaryToBrowseResult);
    }
    await this.loadCourses();
    const qs = new URLSearchParams({ q });
    if (params.courseId) qs.set("course_id", params.courseId);
    if (params.documentId) qs.set("file_id", params.documentId);
    if (params.limit) qs.set("limit", String(params.limit));
    const rows = expectArray<BackendDocumentSearchHit>(
      await fetchJson<unknown>(`${baseUrl()}/api/document-search?${qs}`),
      "document search",
    );
    return rows.map((row) =>
      mapDocumentSearchHit(row, this.courseName(primaryCourseIdFromRefs(row.references))),
    );
  }

  async getDocument(documentId: string) {
    await this.loadCourses();
    try {
      const row = await fetchJson<BackendDocumentView>(
        `${baseUrl()}/api/documents/${encodeURIComponent(documentId)}`,
      );
      let units: BackendDocumentUnitView[] = [];
      try {
        units = expectArray<BackendDocumentUnitView>(
          await fetchJson<unknown>(
            `${baseUrl()}/api/documents/${encodeURIComponent(documentId)}/units`,
          ),
          "document units",
        );
      } catch {
        units = [];
      }
      const courseId = primaryCourseIdFromDocument(row);
      return mapDocumentDetail(row, this.courseName(courseId), units);
    } catch (err) {
      if (err instanceof AcademicApiError && err.kind === "not_found") return null;
      throw err;
    }
  }

  async getDocumentUnits(documentId: string) {
    const units = expectArray<BackendDocumentUnitView>(
      await fetchJson<unknown>(
        `${baseUrl()}/api/documents/${encodeURIComponent(documentId)}/units`,
      ),
      "document units",
    );
    return units.map(mapUnitFromBackend);
  }

  async getDocumentCoverage(courseId: string): Promise<DocumentCoverageSummary> {
    return fetchJson<DocumentCoverageSummary>(
      `${baseUrl()}/api/courses/${encodeURIComponent(courseId)}/document-coverage`,
    );
  }

  async listCourseProfiles() {
    const rows = expectArray<Record<string, unknown>>(
      await fetchJson<unknown>(`${baseUrl()}/api/course-profiles`),
      "course profiles",
    );
    return rows.map(mapCourseProfile);
  }

  async getCourseProfile(courseId: string) {
    try {
      const row = await fetchJson<Record<string, unknown>>(
        `${baseUrl()}/api/course-profiles/${encodeURIComponent(courseId)}`,
      );
      return mapCourseProfile(row);
    } catch (err) {
      if (err instanceof AcademicApiError && err.kind === "not_found") return null;
      throw err;
    }
  }

  async updateCourseProfile(courseId: string, update: Partial<CourseProfileData>) {
    const row = await putJson<Record<string, unknown>>(
      `${baseUrl()}/api/course-profiles/${encodeURIComponent(courseId)}`,
      mapCourseProfileUpdateToBackend(update),
    );
    return mapCourseProfile(row);
  }

  async getStudyContext(courseId: string) {
    try {
      const row = await fetchJson<Record<string, unknown>>(
        `${baseUrl()}/api/study-context/${encodeURIComponent(courseId)}`,
      );
      return mapStudyContext(row);
    } catch (err) {
      if (err instanceof AcademicApiError && err.kind === "not_found") return null;
      throw err;
    }
  }

  async updateStudyContext(courseId: string, update: Partial<import("@/lib/domain/course-intelligence").StudyContext>) {
    const row = await putJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-context/${encodeURIComponent(courseId)}`,
      mapStudyContextUpdateToBackend(update),
    );
    return mapStudyContext(row);
  }

  async resolveCourseRouter(request: CourseRoutingRequest) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/course-router/resolve`,
      mapCourseRoutingRequestToBackend(request),
    );
    return mapCourseRoutingResult(row);
  }

  async resolveAcademicContext(request: CourseRoutingRequest) {
    try {
      const row = await postJson<Record<string, unknown>>(
        `${baseUrl()}/api/academic-context/resolve`,
        mapCourseRoutingRequestToBackend(request),
      );
      return mapAcademicContext(row);
    } catch (err) {
      if (err instanceof AcademicApiError && err.kind === "not_found") return null;
      throw err;
    }
  }

  async getNotifications(options?: { courseId?: string; limit?: number }) {
    const params = new URLSearchParams();
    if (options?.courseId) params.set("course_id", options.courseId);
    if (options?.limit != null) params.set("limit", String(options.limit));
    const qs = params.toString();
    const row = await fetchJson<Record<string, unknown>>(
      `${baseUrl()}/api/notifications${qs ? `?${qs}` : ""}`,
    );
    return mapBackendNotificationList(
      row as { items?: Parameters<typeof mapBackendNotification>[0][]; total?: number },
    );
  }

  async markNotificationRead(notificationId: string) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/notifications/${encodeURIComponent(notificationId)}/read`,
      {},
    );
    return mapBackendNotification(row as Parameters<typeof mapBackendNotification>[0]);
  }

  async dismissNotification(notificationId: string) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/notifications/${encodeURIComponent(notificationId)}/dismiss`,
      {},
    );
    return mapBackendNotification(row as Parameters<typeof mapBackendNotification>[0]);
  }

  async getReminderPreferences() {
    const row = await fetchJson<Record<string, unknown>>(`${baseUrl()}/api/reminders/preferences`);
    return mapBackendReminderPreference(row as Parameters<typeof mapBackendReminderPreference>[0]);
  }

  async saveReminderPreferences(preference: import("@/lib/domain/planning").ReminderPreference) {
    const row = await putJson<Record<string, unknown>>(
      `${baseUrl()}/api/reminders/preferences`,
      mapReminderPreferenceToBackend(preference),
    );
    return mapBackendReminderPreference(row as Parameters<typeof mapBackendReminderPreference>[0]);
  }

  async previewReminderPlan(courseId: string, assignmentId: string) {
    const row = await postJson<Record<string, unknown>>(`${baseUrl()}/api/reminders/preview`, {
      course_id: courseId,
      assignment_id: assignmentId,
    });
    return mapBackendReminderPreview(row as Parameters<typeof mapBackendReminderPreview>[0]);
  }

  async listCalendarLinks() {
    const rows = await fetchJson<Record<string, unknown>[]>(`${baseUrl()}/api/calendar/links`);
    return (Array.isArray(rows) ? rows : []).map((r) =>
      mapBackendCalendarLink(r as Parameters<typeof mapBackendCalendarLink>[0]),
    );
  }

  async linkCalendar(link: { provider: string; calendarId: string; displayName: string }) {
    const row = await postJson<Record<string, unknown>>(`${baseUrl()}/api/calendar/links`, {
      provider: link.provider,
      calendar_id: link.calendarId,
      display_name: link.displayName,
    });
    return mapBackendCalendarLink(row as Parameters<typeof mapBackendCalendarLink>[0]);
  }

  async previewCalendarEvent(courseId: string, assignmentId: string) {
    const row = await postJson<Record<string, unknown>>(`${baseUrl()}/api/calendar/preview`, {
      course_id: courseId,
      assignment_id: assignmentId,
    });
    return mapBackendCalendarPreview(row as Parameters<typeof mapBackendCalendarPreview>[0]);
  }

  async confirmCalendarEvent(confirmation: import("@/lib/domain/planning").CalendarConfirmation) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/calendar/confirm`,
      mapCalendarConfirmationToBackend(confirmation),
    );
    return mapBackendCalendarExecution(row as Parameters<typeof mapBackendCalendarExecution>[0]);
  }

  async previewAutomation(request: import("@/lib/domain/planning").AutomationPreviewRequest) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/automation/preview`,
      mapAutomationRequestToBackend(request),
    );
    return mapBackendAutomationPreview(row as Parameters<typeof mapBackendAutomationPreview>[0]);
  }

  async createStudySession(request: import("@/lib/domain/study-workflows").StudySessionCreateRequest) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions`,
      mapStudySessionCreateToBackend(request),
    );
    return mapBackendStudySession(row);
  }

  async getStudySession(sessionId: string) {
    const row = await fetchJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions/${encodeURIComponent(sessionId)}`,
    );
    return mapBackendStudySession(row);
  }

  async continueStudySession(sessionId: string) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions/${encodeURIComponent(sessionId)}/continue`,
      {},
    );
    return mapBackendStudySession(row);
  }

  async advanceStudySession(sessionId: string, completedStep: number) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions/${encodeURIComponent(sessionId)}/progress`,
      { completed_step: completedStep },
    );
    return mapBackendStudySession(row);
  }

  async createPracticeSession(courseId: string, topic: string, totalQuestions = 5) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions/practice`,
      mapPracticeCreateToBackend(courseId, topic, totalQuestions),
    );
    return mapBackendPracticeSession(row);
  }

  async getPracticeSession(sessionId: string) {
    const row = await fetchJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions/practice/${encodeURIComponent(sessionId)}`,
    );
    return mapBackendPracticeSession(row);
  }

  async answerPracticeSession(sessionId: string, answer: string) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-sessions/practice/${encodeURIComponent(sessionId)}/answer`,
      { answer },
    );
    return mapBackendPracticeFeedback(row);
  }

  async hintPracticeSession(sessionId: string) {
    const row = await postJson<{ hint?: string }>(
      `${baseUrl()}/api/study-sessions/practice/${encodeURIComponent(sessionId)}/hint`,
      {},
    );
    return String(row.hint ?? "");
  }

  async buildStudyGuide(request: import("@/lib/domain/study-workflows").StudyGuideRequest) {
    const row = await postJson<Record<string, unknown>>(
      `${baseUrl()}/api/study-guides`,
      mapStudyGuideRequestToBackend(request),
    );
    return mapBackendStudyGuide(row);
  }

  async askAssistant(prompt: string, courseId?: string): Promise<ChatMessage> {
    void prompt;
    void courseId;
    throw new AcademicApiNotImplementedError("assistant");
  }

  async askAssistantAdvanced(request: AssistantRequest): Promise<ChatMessage> {
    void request;
    throw new AcademicApiNotImplementedError("assistant");
  }

  streamAssistant(request: AssistantRequest): AsyncIterable<AssistantStreamEvent> {
    void request;
    async function* notImplemented(): AsyncGenerator<AssistantStreamEvent> {
      throw new AcademicApiNotImplementedError("assistant streaming");
    }
    return notImplemented();
  }
}

export { baseUrl };
