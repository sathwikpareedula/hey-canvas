"use client";

import { useState } from "react";
import { CalendarConfirmDialog } from "@/components/planning/CalendarConfirmDialog";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { CalendarPreviewResult, ReminderPlanPreview } from "@/lib/domain/planning";
import { formatDueDate } from "@/lib/utils/date";

export function AssignmentPlanningActions({
  courseId,
  assignmentId,
  assignmentTitle,
}: {
  courseId: string;
  assignmentId: string;
  assignmentTitle: string;
}) {
  const api = useAcademicApi();
  const [reminderPreview, setReminderPreview] = useState<ReminderPlanPreview | null>(null);
  const [calendarPreview, setCalendarPreview] = useState<CalendarPreviewResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const previewReminders = async () => {
    setBusy("reminder");
    setError(null);
    setReminderPreview(null);
    try {
      setReminderPreview(await api.previewReminderPlan(courseId, assignmentId));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const previewCalendar = async () => {
    setBusy("calendar");
    setError(null);
    setCalendarPreview(null);
    try {
      setCalendarPreview(await api.previewCalendarEvent(courseId, assignmentId));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-[var(--border)] p-4" aria-label="Planning">
      <h3 className="text-sm font-semibold">Reminders &amp; calendar</h3>
      <p className="text-xs text-[var(--muted)]">
        Preview-only until you confirm calendar actions. No Canvas submission.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => void previewReminders()}
          className="min-h-9 rounded-full border border-[var(--border)] px-3 text-sm"
        >
          {busy === "reminder" ? "Loading…" : "Preview reminder plan"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => void previewCalendar()}
          className="min-h-9 rounded-full border border-[var(--border)] px-3 text-sm"
        >
          {busy === "calendar" ? "Loading…" : "Add to calendar (preview)"}
        </button>
      </div>
      {error ? <ApiErrorPanel error={error} /> : null}
      {reminderPreview ? (
        <div className="rounded-lg bg-[var(--surface-muted)] p-3 text-sm">
          <p className="font-medium">{reminderPreview.title}</p>
          <p className="text-[var(--muted)]">{reminderPreview.summary}</p>
          <p className="mt-1 text-xs">
            {assignmentTitle} · due {formatDueDate(reminderPreview.plan.dueAt)}
          </p>
        </div>
      ) : null}
      {calendarPreview ? (
        <CalendarConfirmDialog
          preview={calendarPreview}
          onClose={() => setCalendarPreview(null)}
        />
      ) : null}
    </section>
  );
}
