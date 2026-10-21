"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { AcademicApiError } from "@/lib/api/errors";
import type { CalendarPreviewResult } from "@/lib/domain/planning";
import { formatDueDate } from "@/lib/utils/date";

export function CalendarConfirmDialog({
  preview,
  onClose,
  onConfirmed,
}: {
  preview: CalendarPreviewResult;
  onClose: () => void;
  onConfirmed?: (message: string) => void;
}) {
  const api = useAcademicApi();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);

  const confirm = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.confirmCalendarEvent(preview.confirmation);
      setResultMessage(result.message);
      onConfirmed?.(result.message);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }, [api, preview.confirmation, onConfirmed]);

  const stale =
    error instanceof AcademicApiError && error.status === 409;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  return (
    <div
      role="alertdialog"
      aria-labelledby="calendar-preview-title"
      aria-describedby="calendar-preview-desc"
      className="rounded-xl border-2 border-[var(--accent)] bg-[var(--surface)] p-4 shadow-lg"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
        Calendar action — review before confirming
      </p>
      <h3 id="calendar-preview-title" className="mt-2 text-base font-semibold break-words">
        {preview.event.summary}
      </h3>
      <p id="calendar-preview-desc" className="mt-2 text-sm text-[var(--muted)]">
        This will create or update an event through your linked calendar provider after you confirm.
        Nothing is written until you press Confirm below.
      </p>
      <dl className="mt-3 space-y-1 text-sm">
        <div className="flex gap-2">
          <dt className="text-[var(--muted)]">Start</dt>
          <dd>{formatDueDate(preview.event.startAt)}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-[var(--muted)]">End</dt>
          <dd>{formatDueDate(preview.event.endAt)}</dd>
        </div>
        {preview.event.description ? (
          <div>
            <dt className="text-[var(--muted)]">Notes</dt>
            <dd className="whitespace-pre-wrap break-words">{preview.event.description}</dd>
          </div>
        ) : null}
        <div className="flex gap-2">
          <dt className="text-[var(--muted)]">Provider</dt>
          <dd>{preview.event.provider}</dd>
        </div>
      </dl>
      {error ? (
        <div className="mt-3">
          <p className="text-sm font-medium">
            {stale ? "This preview is stale" : "Could not confirm calendar action"}
          </p>
          <ApiErrorPanel error={error} />
          {stale ? (
            <p className="mt-1 text-xs text-[var(--muted)]">
              The assignment may have changed. Request a new preview and try again.
            </p>
          ) : null}
        </div>
      ) : null}
      {resultMessage ? (
        <p className="mt-3 text-sm text-[var(--foreground)]" role="status">{resultMessage}</p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {!resultMessage ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void confirm()}
            className="min-h-10 rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] disabled:opacity-50"
          >
            {busy ? "Confirming…" : "Confirm calendar action"}
          </button>
        ) : null}
        <button
          type="button"
          onClick={onClose}
          className="min-h-10 rounded-full border border-[var(--border)] px-4 py-2 text-sm"
        >
          {resultMessage ? "Close" : "Cancel"}
        </button>
      </div>
    </div>
  );
}
