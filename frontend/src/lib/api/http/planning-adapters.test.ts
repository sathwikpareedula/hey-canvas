/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { mapBackendAutomationPreview } from "@/lib/api/http/automation-adapters";
import {
  mapBackendCalendarPreview,
  mapCalendarConfirmationToBackend,
} from "@/lib/api/http/calendar-adapters";
import { mapBackendNotification, mapNotificationHref } from "@/lib/api/http/notification-adapters";
import {
  mapBackendReminderPreference,
  mapBackendReminderPreview,
  mapReminderPreferenceToBackend,
} from "@/lib/api/http/reminder-adapters";

describe("planning API adapters (c31c7cc)", () => {
  it("maps notifications with assignment href", () => {
    const n = mapBackendNotification({
      id: "n1",
      course_id: "c1",
      assignment_id: "a1",
      notification_type: "assignment_due_soon",
      severity: "high",
      title: "Due soon",
      message: "Lab due",
      observed_at: "2026-10-01T12:00:00Z",
      read: false,
      dismissed: false,
    });
    expect(n.href).toBe("/assignments/a1");
    expect(n.severity).toBe("high");
  });

  it("maps material notifications to course", () => {
    expect(
      mapNotificationHref({
        notificationType: "professor_material_new",
        courseId: "c9",
      }),
    ).toBe("/courses/c9");
  });

  it("round-trips reminder preferences", () => {
    const pref = {
      enabled: true,
      leadTimesHours: [48, 3],
      timezone: "America/Chicago",
      courseOverrides: { c1: [12] },
    };
    const backend = mapReminderPreferenceToBackend(pref);
    expect(backend.lead_times_hours).toEqual([48, 3]);
    const back = mapBackendReminderPreference(backend);
    expect(back.leadTimesHours).toEqual([48, 3]);
    expect(back.courseOverrides.c1).toEqual([12]);
  });

  it("maps reminder preview plan", () => {
    const preview = mapBackendReminderPreview({
      title: "Plan",
      summary: "Two reminders",
      plan: {
        plan_id: "p1",
        course_id: "c1",
        assignment_id: "a1",
        due_at: "2026-10-05T00:00:00Z",
        enabled: true,
        reminders: [{ at: "2026-10-04T00:00:00Z", lead_hours: 24, status: "scheduled" }],
      },
    });
    expect(preview.plan.reminders[0]?.leadHours).toBe(24);
  });

  it("maps calendar preview and confirmation body", () => {
    const preview = mapBackendCalendarPreview({
      event: {
        event_id: "e1",
        course_id: "c1",
        assignment_id: "a1",
        summary: "HW",
        start_at: "2026-10-05T12:00:00Z",
        end_at: "2026-10-05T13:00:00Z",
        all_day: false,
        status: "pending",
        provider: "memory",
      },
      confirmation: { action_id: "act1", confirmation_token: "tok" },
    });
    expect(preview.confirmation.confirmationToken).toBe("tok");
    expect(mapCalendarConfirmationToBackend(preview.confirmation)).toEqual({
      action_id: "act1",
      confirmation_token: "tok",
    });
  });

  it("maps automation preview flags", () => {
    const p = mapBackendAutomationPreview({
      operation: "preview_calendar_event",
      title: "Calendar",
      summary: "Preview",
      payload: { summary: "HW 1" },
      requires_confirmation: true,
      safe_to_execute: false,
    });
    expect(p.requiresConfirmation).toBe(true);
    expect(p.safeToExecute).toBe(false);
    expect(p.payload?.summary).toBe("HW 1");
  });
});
