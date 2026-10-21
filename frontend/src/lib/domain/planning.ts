/** Types aligned with CourseProfiles c31c7cc automation APIs. */

export type AcademicNotificationType =
  | "assignment_due_soon"
  | "assignment_due_tomorrow"
  | "assignment_overdue"
  | "assignment_new"
  | "assignment_due_date_changed"
  | "professor_material_new"
  | "professor_material_changed"
  | "exam_upcoming";

export type NotificationSeverity = "low" | "medium" | "high" | "critical";

export type ReminderStatus = "scheduled" | "fired" | "cancelled";

export interface ReminderPreference {
  enabled: boolean;
  leadTimesHours: number[];
  timezone: string;
  courseOverrides: Record<string, number[]>;
}

export interface ReminderOccurrence {
  at: string;
  leadHours: number;
  status: ReminderStatus;
}

export interface ReminderPlan {
  planId: string;
  courseId: string;
  assignmentId: string;
  dueAt: string;
  enabled: boolean;
  reminders: ReminderOccurrence[];
}

export interface ReminderPlanPreview {
  title: string;
  summary: string;
  plan: ReminderPlan;
}

export type CalendarEventStatus = "pending" | "confirmed" | "cancelled";

export interface CalendarEvent {
  eventId: string;
  courseId: string;
  assignmentId: string | null;
  summary: string;
  description: string | null;
  startAt: string;
  endAt: string;
  allDay: boolean;
  status: CalendarEventStatus;
  source: string;
  externalId: string | null;
  provider: string;
}

export interface CalendarLink {
  provider: string;
  calendarId: string;
  displayName: string;
  enabled: boolean;
}

export interface CalendarConfirmation {
  actionId: string;
  confirmationToken: string;
}

export interface CalendarPreviewResult {
  event: CalendarEvent;
  confirmation: CalendarConfirmation;
}

export interface CalendarExecutionResult {
  actionId: string;
  status: CalendarEventStatus;
  event: CalendarEvent;
  message: string;
}

export type AutomationOperation =
  | "list_notifications"
  | "preview_reminder_plan"
  | "preview_calendar_event"
  | "list_linked_calendar_events";

export interface AutomationPreviewRequest {
  operation: AutomationOperation;
  courseId?: string;
  assignmentId?: string;
  query?: string;
}

export interface AutomationPreview {
  operation: AutomationOperation;
  title: string;
  summary: string;
  payload?: Record<string, unknown> | null;
  requiresConfirmation: boolean;
  safeToExecute: boolean;
}
