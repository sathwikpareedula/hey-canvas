"use client";

import { useCallback, useEffect, useState } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { SyncRun } from "@/lib/domain/types";
import { CanvasConnectionGuide } from "@/components/product/CanvasConnectionGuide";
import { syncStatusIsUnhealthy, syncStatusRecoveryHint } from "@/lib/product/student-sync-recovery";
import { formatDueDate, formatRelativeTime } from "@/lib/utils/date";
import Link from "next/link";

function statusLabel(status: SyncRun["status"]) {
  return status.replaceAll("_", " ");
}

export function SyncHistoryView() {
  const api = useAcademicApi();
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [syncBusy, setSyncBusy] = useState(false);

  const reloadRuns = useCallback(() => {
    setLoading(true);
    api
      .getSyncRuns(30)
      .then((r) => {
        setRuns(r);
        setError(null);
      })
      .catch((err) => setError(err))
      .finally(() => setLoading(false));
  }, [api]);

  useEffect(() => {
    let active = true;
    api
      .getSyncRuns(30)
      .then((r) => {
        if (!active) return;
        setRuns(r);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const anyRunning = runs.some((r) => r.status === "running");

  useEffect(() => {
    if (!anyRunning) return;
    const timer = setInterval(() => {
      api
        .getSyncRuns(30)
        .then((r) => {
          setRuns(r);
        })
        .catch(() => {});
    }, 2500);
    return () => clearInterval(timer);
  }, [anyRunning, api]);

  if (loading) return <PageSkeleton />;
  if (error) return <ApiErrorPanel error={error} />;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
        <h2 className="text-base font-semibold">Local Canvas synchronization</h2>
        <p className="text-sm text-[var(--muted)]">
          Read-only sync between UTA Canvas and your local device database. Canvas is strictly read-only —
          no data or grades are ever written to your Canvas account. Previously synced courses and materials
          stay preserved if a run is interrupted.
        </p>
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="button"
            disabled={syncBusy || anyRunning}
            title={anyRunning ? "A Canvas sync is currently running." : undefined}
            className="min-h-10 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            onClick={() => {
              if (syncBusy || anyRunning) return;
              setSyncBusy(true);
              setSyncMsg(null);
              void api
                .triggerCanvasSync()
                .then((result) => {
                  setSyncMsg(result.message);
                  if (result.accepted) {
                    setTimeout(() => reloadRuns(), 1500);
                  }
                })
                .catch(() => setSyncMsg("Could not start sync. Confirm the academic service is running."))
                .finally(() => setSyncBusy(false));
            }}
          >
            {syncBusy ? "Starting sync…" : anyRunning ? "Sync in progress…" : "Sync Canvas now"}
          </button>
          <button
            type="button"
            disabled={loading}
            className="min-h-10 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm font-medium hover:bg-[var(--surface)] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            onClick={() => reloadRuns()}
          >
            {loading ? "Checking…" : "Refresh history"}
          </button>
        </div>
        {syncMsg ? (
          <p className="text-xs text-[var(--muted)]" role="status">{syncMsg}</p>
        ) : null}
      </div>
      <CanvasConnectionGuide compact />
      <p className="text-xs text-[var(--muted)]">
        To verify credentials without syncing, check{" "}
        <Link href="/settings#connection" className="underline">Settings → Connection</Link>.
      </p>
      {!runs.length ? (
        <EmptyState
          title="No sync history"
          description="Runs appear after local read-only Canvas synchronization via the backend CLI or the button above."
        />
      ) : (
        <ul className="space-y-3">
          {runs.map((run) => (
            <li key={run.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium capitalize">{statusLabel(run.status)}</p>
                  <p className="text-xs text-[var(--muted)]">
                    Run #{run.id} · {run.trigger} · {formatRelativeTime(run.startedAt)}
                  </p>
                </div>
                <span className="text-xs text-[var(--muted)]">
                  {run.changeEventsCreated} changes · {run.errorCount} errors
                </span>
              </div>
              {run.finishedAt ? (
                <p className="mt-2 text-xs text-[var(--muted)]">
                  Finished {formatDueDate(run.finishedAt)}
                </p>
              ) : null}
              {run.changeSummary ? (
                <p className="mt-2 text-xs">
                  Summary:{" "}
                  {Object.entries(run.changeSummary)
                    .map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`)
                    .join(" · ")}
                </p>
              ) : null}
              {syncStatusIsUnhealthy(run.status) && syncStatusRecoveryHint(run) ? (
                <p className="mt-2 text-xs text-[var(--warn-text)]">{syncStatusRecoveryHint(run)}</p>
              ) : null}
              {run.errors?.length ? (
                <ul className="mt-2 space-y-1 text-xs text-[var(--warn-text)]">
                  {run.errors.map((e, i) => (
                    <li key={i}>
                      {e.stage}: {e.message}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
