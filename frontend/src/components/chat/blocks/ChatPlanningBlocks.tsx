"use client";

import { useState } from "react";
import { AutomationPreviewCard } from "@/components/hey-canvas/AutomationPreviewCard";
import { CalendarConfirmDialog } from "@/components/planning/CalendarConfirmDialog";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type {
  CalendarPreviewResult,
  ReminderPlanPreview,
} from "@/lib/domain/planning";
import type { AppNotification } from "@/lib/domain/types";
import type { StudyGuide, StudySession } from "@/lib/domain/study-workflows";
import Link from "next/link";
import { buildStudyGuideUrl, buildStudyWorkspaceUrl } from "@/lib/navigation/study-links";
import {
  studySessionDurationLabel,
  studySessionGoalLabel,
  studySessionProgressLabel,
} from "@/lib/study/present-study-session";
import { finiteNumber } from "@/lib/utils/numbers";

export function ChatStudyPlanBlock({ session }: { session: StudySession }) {
  const goal = studySessionGoalLabel(session);
  const duration = studySessionDurationLabel(session.durationMinutes);
  const progress = studySessionProgressLabel(session.progress);
  const studyHref = buildStudyWorkspaceUrl({
    courseId: session.courseId || undefined,
    continueSession: true,
  });

  return (
    <section aria-label="Study plan" className="rounded-xl border border-[var(--border)] p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Study plan</p>
      <p className="mt-1 text-sm font-medium break-words">{goal}</p>
      <p className="text-xs text-[var(--muted)]">
        {duration} · {progress}
      </p>
      {session.steps.length ? (
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
          {session.steps.map((step) => (
            <li key={step.order} className="break-words">
              {step.title}
              <span className="text-[var(--muted)]">
                {" "}
                · {finiteNumber(step.minutes, 15)} min
              </span>
              {step.status === "complete" ? (
                <span className="ml-1 text-xs text-[var(--muted)]">(done)</span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-[var(--muted)]">
          Steps will appear when the backend returns a full study session plan.
        </p>
      )}
      <Link href={studyHref} className="mt-2 inline-block text-xs underline">
        Open study session
      </Link>
    </section>
  );
}

export function ChatStudyGuideBlock({
  guide,
  courseId,
}: {
  guide: StudyGuide;
  courseId?: string;
}) {
  const href = courseId
    ? buildStudyGuideUrl({ courseId, topic: guide.scope || guide.title })
    : "/study/guide";
  return (
    <section aria-label="Study guide" className="rounded-xl border border-[var(--border)] p-3">
      <p className="text-sm font-semibold break-words">{guide.title}</p>
      {guide.keyConcepts.length ? (
        <ul className="mt-2 list-disc pl-5 text-sm">
          {guide.keyConcepts.slice(0, 6).map((c) => (
            <li key={c} className="break-words">{c}</li>
          ))}
        </ul>
      ) : null}
      <Link href={href} className="mt-2 inline-block text-xs underline">
        View full study guide
      </Link>
    </section>
  );
}

export function ChatNotificationSummaryBlock({ items }: { items: AppNotification[] }) {
  if (!items.length) {
    return <p className="text-sm text-[var(--muted)]">No notifications to show.</p>;
  }
  return (
    <ul className="space-y-2" aria-label="Notifications">
      {items.slice(0, 8).map((n) => (
        <li key={n.id} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm">
          <p className="font-medium break-words">{n.title}</p>
          <p className="text-xs text-[var(--muted)] break-words">{n.body}</p>
        </li>
      ))}
    </ul>
  );
}

export function ChatReminderPreviewBlock({ preview }: { preview: ReminderPlanPreview }) {
  return (
    <div className="rounded-xl border border-[var(--border)] p-3 text-sm">
      <p className="font-medium">{preview.title}</p>
      <p className="text-[var(--muted)]">{preview.summary}</p>
      <p className="mt-1 text-xs">
        {preview.plan.reminders.length} reminder(s) scheduled before due date.
      </p>
    </div>
  );
}

export function ChatCalendarPreviewBlock({
  preview,
}: {
  preview: CalendarPreviewResult;
}) {
  const api = useAcademicApi();
  const [confirmPreview, setConfirmPreview] = useState<CalendarPreviewResult | null>(null);
  const [busy, setBusy] = useState(false);

  const openConfirmFlow = async () => {
    const { courseId, assignmentId } = preview.event;
    if (!courseId || !assignmentId) {
      if (preview.confirmation.confirmationToken) {
        setConfirmPreview(preview);
      }
      return;
    }
    setBusy(true);
    try {
      setConfirmPreview(await api.previewCalendarEvent(courseId, assignmentId));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] p-3 text-sm space-y-2">
      <p className="font-medium break-words">{preview.event.summary}</p>
      <p className="text-xs text-[var(--muted)]">
        Calendar preview — confirmation required before anything is written.
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={() => void openConfirmFlow()}
        className="min-h-9 rounded-full bg-[var(--accent)] px-3 text-xs font-medium text-[var(--accent-fg)]"
      >
        Review and confirm
      </button>
      {confirmPreview ? (
        <CalendarConfirmDialog preview={confirmPreview} onClose={() => setConfirmPreview(null)} />
      ) : null}
    </div>
  );
}

export function ChatCalendarResultBlock({
  result,
}: {
  result: import("@/lib/domain/planning").CalendarExecutionResult;
}) {
  return (
    <p className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" role="status">
      {result.message}
    </p>
  );
}

export function ChatAutomationFromPreview({
  operation,
  title,
  summary,
  courseId,
  assignmentId,
}: {
  operation: "preview_reminder_plan" | "preview_calendar_event";
  title: string;
  summary: string;
  courseId?: string;
  assignmentId?: string;
}) {
  return (
    <AutomationPreviewCard
      preview={{
        operation,
        title,
        summary,
        payload: null,
        requiresConfirmation: operation === "preview_calendar_event",
        safeToExecute: operation !== "preview_calendar_event",
      }}
      courseId={courseId}
      assignmentId={assignmentId}
      onClose={() => undefined}
    />
  );
}
