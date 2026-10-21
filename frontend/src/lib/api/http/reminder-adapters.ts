import type { ReminderPlanPreview, ReminderPreference } from "@/lib/domain/planning";

type BackendPreference = {
  enabled: boolean;
  lead_times_hours: number[] | readonly number[];
  timezone: string;
  course_overrides: Record<string, number[] | readonly number[]>;
};

type BackendOccurrence = {
  at: string;
  lead_hours: number;
  status: string;
};

type BackendPlan = {
  plan_id: string;
  course_id: string;
  assignment_id: string;
  due_at: string;
  enabled: boolean;
  reminders: BackendOccurrence[];
};

type BackendPreview = {
  title: string;
  summary: string;
  plan: BackendPlan;
};

export function mapReminderPreferenceToBackend(pref: ReminderPreference): BackendPreference {
  const course_overrides: Record<string, number[]> = {};
  for (const [courseId, hours] of Object.entries(pref.courseOverrides)) {
    course_overrides[courseId] = [...hours];
  }
  return {
    enabled: pref.enabled,
    lead_times_hours: [...pref.leadTimesHours],
    timezone: pref.timezone,
    course_overrides,
  };
}

export function mapBackendReminderPreference(row: BackendPreference): ReminderPreference {
  const courseOverrides: Record<string, number[]> = {};
  for (const [courseId, hours] of Object.entries(row.course_overrides ?? {})) {
    courseOverrides[courseId] = Array.isArray(hours) ? [...hours] : [];
  }
  return {
    enabled: row.enabled,
    leadTimesHours: Array.isArray(row.lead_times_hours) ? [...row.lead_times_hours] : [],
    timezone: row.timezone,
    courseOverrides,
  };
}

function mapBackendPlan(row: BackendPlan) {
  return {
    planId: row.plan_id,
    courseId: row.course_id,
    assignmentId: row.assignment_id,
    dueAt: row.due_at,
    enabled: row.enabled,
    reminders: (row.reminders ?? []).map((r) => ({
      at: r.at,
      leadHours: r.lead_hours,
      status: r.status as "scheduled" | "fired" | "cancelled",
    })),
  };
}

export function mapBackendReminderPreview(row: BackendPreview): ReminderPlanPreview {
  return {
    title: row.title,
    summary: row.summary,
    plan: mapBackendPlan(row.plan),
  };
}
