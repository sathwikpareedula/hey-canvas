import { AcademicApiMalformedError } from "@/lib/api/errors";
import type {
  Assignment,
  ChangeEvent,
  Course,
  DeadlineWindow,
  SyncRun,
  SyncRunStatus,
} from "@/lib/domain/types";

const COURSE_COLORS = ["#2563eb", "#7c3aed", "#059669", "#dc2626", "#d97706", "#0891b2"];

function courseColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash + id.charCodeAt(i)) % COURSE_COLORS.length;
  return COURSE_COLORS[hash];
}

export interface BackendCourse {
  canvas_course_id: string;
  course_code: string | null;
  course_name: string | null;
  term_name: string | null;
}

export interface BackendAssignment {
  canvas_assignment_id: string;
  canvas_course_id: string;
  name: string | null;
  description_html: string | null;
  due_at: string | null;
  points_possible: number | null;
  workflow_state: string | null;
  html_url: string | null;
  published: boolean | null;
}

export interface BackendChange {
  id: number;
  entity_type: string;
  entity_external_id: string;
  course_canvas_id: string | null;
  event_type: string;
  field_name: string | null;
  old_value: unknown;
  new_value: unknown;
  observed_at: string;
}

export interface BackendSyncRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: SyncRunStatus;
  trigger: string;
  change_events_created: number;
  error_count: number;
  stage_results?: Record<string, unknown>;
  change_summary?: Record<string, number>;
  errors?: Array<{ message?: string; stage?: string }>;
}

export function mapCourse(row: BackendCourse): Course {
  if (!row?.canvas_course_id || typeof row.canvas_course_id !== "string") {
    throw new AcademicApiMalformedError("Course row missing canvas_course_id");
  }
  return {
    id: row.canvas_course_id,
    name: row.course_name ?? "Untitled course",
    code: row.course_code ?? undefined,
    term: row.term_name ?? undefined,
    color: courseColor(row.canvas_course_id),
  };
}

export function mapAssignment(row: BackendAssignment, window?: DeadlineWindow): Assignment {
  if (!row?.canvas_assignment_id || !row?.canvas_course_id) {
    throw new AcademicApiMalformedError("Assignment row missing identifiers");
  }
  return {
    id: row.canvas_assignment_id,
    courseId: row.canvas_course_id,
    title: row.name ?? "Untitled assignment",
    dueAt: row.due_at,
    pointsPossible: row.points_possible,
    workflowState: row.workflow_state,
    deadlineWindow: window,
    htmlUrl: row.html_url,
  };
}

export function stripHtmlToPlain(html: string | null | undefined): string {
  if (!html) return "";
  return html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function mapChange(row: BackendChange, courseName?: string): ChangeEvent {
  const fmt = (v: unknown): string | null => {
    if (v === null || v === undefined) return null;
    if (typeof v === "string") return v;
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  };
  return {
    id: String(row.id),
    observedAt: row.observed_at,
    courseId: row.course_canvas_id,
    courseName,
    entityType: row.entity_type,
    entityLabel: row.entity_external_id,
    eventType: row.event_type,
    fieldName: row.field_name,
    oldValue: fmt(row.old_value),
    newValue: fmt(row.new_value),
  };
}

const SYNC_STATUSES: SyncRunStatus[] = [
  "running",
  "succeeded",
  "partially_succeeded",
  "failed",
  "interrupted",
];

export function mapSyncRun(row: BackendSyncRun): SyncRun {
  if (row == null || typeof row !== "object") {
    throw new AcademicApiMalformedError("Sync run row was not an object");
  }
  if (typeof row.id !== "number" || !Number.isFinite(row.id)) {
    throw new AcademicApiMalformedError("Sync run row missing id");
  }
  if (typeof row.started_at !== "string" || !row.started_at) {
    throw new AcademicApiMalformedError("Sync run row missing started_at");
  }
  if (!SYNC_STATUSES.includes(row.status)) {
    throw new AcademicApiMalformedError("Sync run row has invalid status");
  }
  return {
    id: row.id,
    startedAt: row.started_at,
    finishedAt: row.finished_at,
    status: row.status,
    trigger: row.trigger,
    changeEventsCreated: row.change_events_created,
    errorCount: row.error_count,
    stageResults: row.stage_results,
    changeSummary: row.change_summary,
    errors: row.errors?.map((e) => ({
      stage: e.stage ?? "unknown",
      message: e.message ?? "Error",
    })),
  };
}
