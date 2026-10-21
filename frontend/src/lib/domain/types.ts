/** UI-facing domain contracts — not 1:1 with backend tables. */

import type { AssistantStatus } from "@/lib/domain/assistant";

export type DeadlineWindow =
  | "today"
  | "tomorrow"
  | "this_week"
  | "next_week"
  | "next_7_days"
  | "upcoming"
  | "past_due_time";

export type SyncRunStatus =
  | "running"
  | "succeeded"
  | "partially_succeeded"
  | "failed"
  | "interrupted";

export interface Course {
  id: string;
  name: string;
  code?: string;
  term?: string;
  color?: string;
}

export interface Assignment {
  id: string;
  courseId: string;
  title: string;
  dueAt: string | null;
  pointsPossible?: number | null;
  workflowState?: string | null;
  /** Backend deadline semantics only — not submission status. */
  deadlineWindow?: DeadlineWindow;
  htmlUrl?: string | null;
  published?: boolean | null;
}

export interface AssignmentDetail extends Assignment {
  descriptionPlainText: string;
  moduleContext?: string | null;
  relatedDocumentIds?: string[];
  recentChangeIds?: string[];
}

export interface Module {
  id: string;
  courseId: string;
  name: string;
  position: number;
}

export interface ModuleItem {
  id: string;
  moduleId: string;
  courseId: string;
  title: string;
  type: string;
  position: number;
}

export interface AcademicFile {
  id: string;
  courseId: string;
  displayName: string;
  contentType?: string | null;
  moduleItemId?: string | null;
}

export type DocumentType = "pdf" | "slides" | "notes" | "assignment" | "other";

export interface DocumentUnit {
  page?: number;
  slide?: number;
  section?: string;
  label: string;
}

export interface Provenance {
  courseId: string;
  courseName: string;
  /** When mapped from assistant evidence identifiers (canvas file / document id). */
  documentId?: string;
  moduleName?: string;
  moduleItemTitle?: string;
  fileName?: string;
  documentTitle?: string;
  unit?: DocumentUnit;
  excerpt?: string;
  isStale?: boolean;
}

export interface Document {
  id: string;
  courseId: string;
  title: string;
  documentType: DocumentType;
}

export interface DocumentSearchResult {
  documentId: string;
  title: string;
  courseId: string;
  courseName: string;
  snippet: string;
  unit: DocumentUnit;
  provenance: Provenance;
  documentType: DocumentType;
  isStale?: boolean;
}

export interface ChangeEvent {
  id: string;
  observedAt: string;
  courseId: string | null;
  courseName?: string;
  entityType: string;
  entityLabel: string;
  eventType: string;
  fieldName?: string | null;
  oldValue?: string | null;
  newValue?: string | null;
}

export interface SyncRunErrorSummary {
  stage: string;
  message: string;
}

export interface SyncRun {
  id: number;
  startedAt: string;
  finishedAt: string | null;
  status: SyncRunStatus;
  trigger: string;
  changeEventsCreated: number;
  errorCount: number;
  stageResults?: Record<string, unknown>;
  changeSummary?: Record<string, number>;
  errors?: SyncRunErrorSummary[];
}

export type DocumentIngestionState =
  | "pending"
  | "indexed"
  | "searchable"
  | "failed";

export interface DocumentCoverageSummary {
  canvas_course_id: string;
  known_files: number;
  eligible_files: number;
  indexed_current: number;
  indexed_stale: number;
  awaiting_download: number;
  needs_ocr: number;
  unsupported: number;
  failed: number;
}

export interface DocumentSummary {
  documentId: string;
  title: string;
  courseId: string;
  courseName: string;
  documentType: DocumentType;
  ingestionState: DocumentIngestionState;
  isStale: boolean;
  needsOcr: boolean;
  unitCount: number;
  backendStatus: string;
}

export interface DocumentDetail {
  id: string;
  courseId: string;
  courseName: string;
  title: string;
  documentType: DocumentType;
  provenance: Provenance;
  previewPlainText: string;
  ingestionState: DocumentIngestionState;
  units?: DocumentUnit[];
  isStale?: boolean;
  needsOcr?: boolean;
  backendStatus?: string;
  technical?: {
    contentSha256?: string;
    parserVersion?: string;
  };
}

export interface DashboardSnapshot {
  nextDeadline: Assignment | null;
  dueToday: Assignment[];
  dueTomorrow: Assignment[];
  thisWeek: Assignment[];
  upcomingWorkload: Assignment[];
  recentChanges: ChangeEvent[];
  suggestedMaterials: DocumentSearchResult[];
  lastSync: SyncRun | null;
}

export type NotificationCategory =
  | "deadline"
  | "canvas_change"
  | "new_material"
  | "sync_problem"
  | "assistant";

export interface AppNotification {
  id: string;
  category: NotificationCategory;
  notificationType?: import("@/lib/domain/planning").AcademicNotificationType;
  severity?: import("@/lib/domain/planning").NotificationSeverity;
  title: string;
  body: string;
  createdAt: string;
  dueAt?: string;
  read: boolean;
  dismissed?: boolean;
  courseId?: string;
  assignmentId?: string;
  href?: string;
}

export type ChatRole = "user" | "assistant";

export interface AssistantSource {
  id: string;
  provenance: Provenance;
}

export type AssistantBlockType =
  | "text"
  | "deadlines"
  | "assignment_summary"
  | "course"
  | "study"
  | "study_plan"
  | "document_answer"
  | "changes_summary"
  | "practice_question"
  | "practice_feedback"
  | "study_guide"
  | "notification_summary"
  | "reminder_preview"
  | "calendar_action_preview"
  | "calendar_action_result"
  | "warning"
  | "error";

export interface AssistantBlock {
  type: AssistantBlockType;
  content?: string;
  assignments?: Assignment[];
  course?: Course;
  studyTips?: string[];
  studySession?: import("@/lib/domain/study-workflows").StudySession;
  practiceSession?: import("@/lib/domain/study-workflows").PracticeSession;
  practiceFeedback?: import("@/lib/domain/study-workflows").PracticeFeedback;
  studyGuide?: import("@/lib/domain/study-workflows").StudyGuide;
  notificationItems?: AppNotification[];
  reminderPreview?: import("@/lib/domain/planning").ReminderPlanPreview;
  calendarPreview?: import("@/lib/domain/planning").CalendarPreviewResult;
  calendarResult?: import("@/lib/domain/planning").CalendarExecutionResult;
  sources?: AssistantSource[];
  changes?: ChangeEvent[];
  followUps?: string[];
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  createdAt: string;
  text?: string;
  blocks?: AssistantBlock[];
  status?: AssistantStatus;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  courseId?: string;
  updatedAt: string;
}

export interface DeadlinesGrouped {
  today: Assignment[];
  tomorrow: Assignment[];
  thisWeek: Assignment[];
}

export interface DocumentSearchParams {
  query: string;
  courseId?: string;
  documentId?: string;
  documentType?: DocumentType;
  limit?: number;
}

export interface DocumentListParams {
  courseId?: string;
  status?: string;
  documentType?: DocumentType;
  limit?: number;
}

export interface AssignmentFilters {
  courseId?: string;
  window?: DeadlineWindow;
}
