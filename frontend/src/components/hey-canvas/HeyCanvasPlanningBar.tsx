"use client";

import { useState } from "react";
import { AutomationPreviewCard } from "@/components/hey-canvas/AutomationPreviewCard";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { AutomationPreview } from "@/lib/domain/planning";

export function HeyCanvasPlanningBar({
  courseId,
  assignmentId,
}: {
  courseId: string;
  assignmentId: string;
}) {
  const api = useAcademicApi();
  const [preview, setPreview] = useState<AutomationPreview | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (operation: AutomationPreview["operation"]) => {
    setBusy(true);
    try {
      const result = await api.previewAutomation({
        operation,
        courseId,
        assignmentId,
      });
      setPreview(result);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)]/50 p-3">
      <p className="text-xs font-medium text-[var(--muted)]">Planning actions (backend preview)</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          className="text-xs underline"
          onClick={() => void run("preview_reminder_plan")}
        >
          Remind me about this
        </button>
        <button
          type="button"
          disabled={busy}
          className="text-xs underline"
          onClick={() => void run("preview_calendar_event")}
        >
          Put on my calendar
        </button>
      </div>
      {preview ? (
        <AutomationPreviewCard
          preview={preview}
          courseId={courseId}
          assignmentId={assignmentId}
          onClose={() => setPreview(null)}
        />
      ) : null}
    </div>
  );
}
