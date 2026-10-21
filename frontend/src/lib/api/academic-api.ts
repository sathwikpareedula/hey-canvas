import type {
  AssistantRequest,
  AssistantStreamEvent,
} from "@/lib/domain/assistant";
import type {
  AcademicContext,
  CourseProfile,
  CourseProfileData,
  CourseRoutingRequest,
  CourseRoutingResult,
  StudyContext,
} from "@/lib/domain/course-intelligence";
import type {
  AutomationPreview,
  AutomationPreviewRequest,
  CalendarConfirmation,
  CalendarExecutionResult,
  CalendarLink,
  CalendarPreviewResult,
  ReminderPlanPreview,
  ReminderPreference,
} from "@/lib/domain/planning";
import type {
  AppNotification,
  Assignment,
  AssignmentDetail,
  AssignmentFilters,
  ChangeEvent,
  ChatMessage,
  Course,
  DashboardSnapshot,
  DeadlinesGrouped,
  DocumentDetail,
  DocumentListParams,
  DocumentSearchParams,
  DocumentSearchResult,
  DocumentSummary,
  Module,
  ModuleItem,
  SyncRun,
} from "@/lib/domain/types";

export interface AcademicApi {
  getCourses(): Promise<Course[]>;
  getCourse(courseId: string): Promise<Course | null>;
  getAssignments(filters?: AssignmentFilters): Promise<Assignment[]>;
  getAssignment(assignmentId: string): Promise<AssignmentDetail | null>;
  getDeadlines(): Promise<DeadlinesGrouped>;
  getDashboard(): Promise<DashboardSnapshot>;
  getModules(courseId?: string): Promise<Module[]>;
  getModuleItems(courseId: string): Promise<ModuleItem[]>;
  getChanges(limit?: number): Promise<ChangeEvent[]>;
  getSyncRuns(limit?: number): Promise<SyncRun[]>;
  getSyncRun(runId: number): Promise<SyncRun | null>;
  getLatestSyncRun(): Promise<SyncRun | null>;
  probeCanvasConnection(): Promise<"ready" | "not_configured" | "unavailable">;
  triggerCanvasSync(): Promise<{ accepted: boolean; message: string }>;
  listDocuments(params?: DocumentListParams): Promise<DocumentSummary[]>;
  searchDocuments(params: DocumentSearchParams): Promise<DocumentSearchResult[]>;
  getDocument(documentId: string): Promise<DocumentDetail | null>;
  getDocumentUnits(documentId: string): Promise<import("@/lib/domain/types").DocumentUnit[]>;
  getDocumentCoverage(courseId: string): Promise<import("@/lib/domain/types").DocumentCoverageSummary>;
  listCourseProfiles(): Promise<CourseProfile[]>;
  getCourseProfile(courseId: string): Promise<CourseProfile | null>;
  updateCourseProfile(
    courseId: string,
    update: Partial<CourseProfileData>,
  ): Promise<CourseProfile>;
  getStudyContext(courseId: string): Promise<StudyContext | null>;
  updateStudyContext(courseId: string, update: Partial<StudyContext>): Promise<StudyContext>;
  resolveCourseRouter(request: CourseRoutingRequest): Promise<CourseRoutingResult>;
  resolveAcademicContext(request: CourseRoutingRequest): Promise<AcademicContext | null>;
  getNotifications(options?: { courseId?: string; limit?: number }): Promise<AppNotification[]>;
  markNotificationRead(notificationId: string): Promise<AppNotification>;
  dismissNotification(notificationId: string): Promise<AppNotification>;
  getReminderPreferences(): Promise<ReminderPreference>;
  saveReminderPreferences(preference: ReminderPreference): Promise<ReminderPreference>;
  previewReminderPlan(courseId: string, assignmentId: string): Promise<ReminderPlanPreview>;
  listCalendarLinks(): Promise<CalendarLink[]>;
  linkCalendar(link: {
    provider: string;
    calendarId: string;
    displayName: string;
  }): Promise<CalendarLink>;
  previewCalendarEvent(courseId: string, assignmentId: string): Promise<CalendarPreviewResult>;
  confirmCalendarEvent(confirmation: CalendarConfirmation): Promise<CalendarExecutionResult>;
  previewAutomation(request: AutomationPreviewRequest): Promise<AutomationPreview>;
  createStudySession(
    request: import("@/lib/domain/study-workflows").StudySessionCreateRequest,
  ): Promise<import("@/lib/domain/study-workflows").StudySession>;
  getStudySession(sessionId: string): Promise<import("@/lib/domain/study-workflows").StudySession>;
  continueStudySession(
    sessionId: string,
  ): Promise<import("@/lib/domain/study-workflows").StudySession>;
  advanceStudySession(
    sessionId: string,
    completedStep: number,
  ): Promise<import("@/lib/domain/study-workflows").StudySession>;
  createPracticeSession(
    courseId: string,
    topic: string,
    totalQuestions?: number,
  ): Promise<import("@/lib/domain/study-workflows").PracticeSession>;
  getPracticeSession(
    sessionId: string,
  ): Promise<import("@/lib/domain/study-workflows").PracticeSession>;
  answerPracticeSession(
    sessionId: string,
    answer: string,
  ): Promise<import("@/lib/domain/study-workflows").PracticeFeedback>;
  hintPracticeSession(sessionId: string): Promise<string>;
  buildStudyGuide(
    request: import("@/lib/domain/study-workflows").StudyGuideRequest,
  ): Promise<import("@/lib/domain/study-workflows").StudyGuide>;
  askAssistant(prompt: string, courseId?: string): Promise<ChatMessage>;
  askAssistantAdvanced(request: AssistantRequest): Promise<ChatMessage>;
  streamAssistant?(request: AssistantRequest): AsyncIterable<AssistantStreamEvent>;
}
