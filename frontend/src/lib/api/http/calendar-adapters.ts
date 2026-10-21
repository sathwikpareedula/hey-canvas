import type {
  CalendarConfirmation,
  CalendarEvent,
  CalendarExecutionResult,
  CalendarLink,
  CalendarPreviewResult,
} from "@/lib/domain/planning";

type BackendEvent = {
  event_id: string;
  course_id: string;
  assignment_id?: string | null;
  summary: string;
  description?: string | null;
  start_at: string;
  end_at: string;
  all_day: boolean;
  status: string;
  source?: string;
  external_id?: string | null;
  provider: string;
};

type BackendConfirmation = {
  action_id: string;
  confirmation_token: string;
};

type BackendLink = {
  provider: string;
  calendar_id: string;
  display_name: string;
  enabled: boolean;
};

export function mapBackendCalendarEvent(row: BackendEvent): CalendarEvent {
  return {
    eventId: row.event_id,
    courseId: row.course_id,
    assignmentId: row.assignment_id ?? null,
    summary: row.summary,
    description: row.description ?? null,
    startAt: row.start_at,
    endAt: row.end_at,
    allDay: row.all_day,
    status: row.status as CalendarEvent["status"],
    source: row.source ?? "canvas",
    externalId: row.external_id ?? null,
    provider: row.provider,
  };
}

export function mapBackendCalendarLink(row: BackendLink): CalendarLink {
  return {
    provider: row.provider,
    calendarId: row.calendar_id,
    displayName: row.display_name,
    enabled: row.enabled,
  };
}

export function mapBackendCalendarPreview(body: {
  event: BackendEvent;
  confirmation: BackendConfirmation;
}): CalendarPreviewResult {
  return {
    event: mapBackendCalendarEvent(body.event),
    confirmation: {
      actionId: body.confirmation.action_id,
      confirmationToken: body.confirmation.confirmation_token,
    },
  };
}

export function mapCalendarConfirmationToBackend(
  confirmation: CalendarConfirmation,
): BackendConfirmation {
  return {
    action_id: confirmation.actionId,
    confirmation_token: confirmation.confirmationToken,
  };
}

export function mapBackendCalendarExecution(body: {
  action_id: string;
  status: string;
  event: BackendEvent;
  message: string;
}): CalendarExecutionResult {
  return {
    actionId: body.action_id,
    status: body.status as CalendarEvent["status"],
    event: mapBackendCalendarEvent(body.event),
    message: body.message,
  };
}
