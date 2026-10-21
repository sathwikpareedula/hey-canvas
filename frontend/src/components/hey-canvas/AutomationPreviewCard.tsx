"use client";

import { useState } from "react";
import { CalendarConfirmDialog } from "@/components/planning/CalendarConfirmDialog";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { AutomationPreview, CalendarPreviewResult } from "@/lib/domain/planning";

export function AutomationPreviewCard({
  preview,
  courseId,
  assignmentId,
  onClose,
}: {
  preview: AutomationPreview;
  courseId?: string;
  assignmentId?: string;
  onClose: () => void;
}) {
  const api = useAcademicApi();
  const [calendarPreview, setCalendarPreview] = useState<CalendarPreviewResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [reminderSummary, setReminderSummary] = useState<string | null>(null);

  const openCalendarFlow = async () => {
    if (!courseId || !assignmentId) return;
    setError(null);
    try {
      setCalendarPreview(await api.previewCalendarEvent(courseId, assignmentId));
    } catch (err) {
      setError(err);
    }
  };

  const openReminderFlow = async () => {
    if (!courseId || !assignmentId) return;
    setError(null);
    try {
      const plan = await api.previewReminderPlan(courseId, assignmentId);
      setReminderSummary(`${plan.title} — ${plan.summary}`);
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Structured preview</p>
          <p className="text-sm font-medium">{preview.title}</p>
          <p className="text-xs text-[var(--muted)]">{preview.summary}</p>
        </div>
        <button type="button" className="text-xs underline" onClick={onClose}>
          Close
        </button>
      </div>
      {preview.requiresConfirmation ? (
        <p className="text-xs text-[var(--warn-text)]">
          External calendar changes require an explicit confirmation step.
        </p>
      ) : null}
      {error ? <ApiErrorPanel error={error} /> : null}
      {preview.payload?.summary && typeof preview.payload.summary === "string" ? (
        <p className="text-xs text-[var(--muted)]">{preview.payload.summary}</p>
      ) : null}
      {reminderSummary ? (
        <p className="text-sm" role="status">{reminderSummary}</p>
      ) : null}
      {preview.operation === "preview_calendar_event" && courseId && assignmentId ? (
        <button
          type="button"
          onClick={() => void openCalendarFlow()}
          className="min-h-9 rounded-full bg-[var(--accent)] px-3 text-xs font-medium text-[var(--accent-fg)]"
        >
          Review calendar preview
        </button>
      ) : null}
      {preview.operation === "preview_reminder_plan" && courseId && assignmentId ? (
        <button
          type="button"
          onClick={() => void openReminderFlow()}
          className="min-h-9 rounded-full border border-[var(--border)] px-3 text-xs"
        >
          View reminder plan
        </button>
      ) : null}
      {calendarPreview ? (
        <CalendarConfirmDialog preview={calendarPreview} onClose={() => setCalendarPreview(null)} />
      ) : null}
    </div>
  );
}
