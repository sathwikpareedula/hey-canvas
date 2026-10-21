"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import Link from "next/link";
import { useDemoDataBadge } from "@/hooks/useDemoDataBadge";
import type { SyncRun, SyncRunStatus } from "@/lib/domain/types";
import {
  syncStatusIsUnhealthy,
  syncStatusRecoveryHint,
} from "@/lib/product/student-sync-recovery";
import { formatRelativeTime } from "@/lib/utils/date";

function statusLabel(status: SyncRunStatus): string {
  switch (status) {
    case "running":
      return "Sync running";
    case "succeeded":
      return "Last sync succeeded";
    case "partially_succeeded":
      return "Partially succeeded";
    case "failed":
      return "Sync failed";
    case "interrupted":
      return "Sync interrupted";
    default:
      return status;
  }
}

function statusDot(status: SyncRunStatus): string {
  const pulse =
    status === "running" ? "animate-pulse motion-reduce:animate-none" : "";
  switch (status) {
    case "running":
      return `bg-[var(--accent)] ${pulse}`;
    case "succeeded":
      return "bg-emerald-500";
    case "partially_succeeded":
      return "bg-amber-500";
    case "failed":
    case "interrupted":
      return "bg-red-500";
    default:
      return "bg-[var(--muted)]";
  }
}

function subscribeNever(): () => void {
  return () => undefined;
}

export function SyncStatus({ variant = "sidebar" }: { variant?: "sidebar" | "inline" }) {
  const api = useAcademicApi();
  const { mode, connection, checking } = useBackendStatus();
  const showDemoBadge = useDemoDataBadge();
  const backendOffline = mode === "http" && !checking && connection !== "connected";
  const [run, setRun] = useState<SyncRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [relativeTime, setRelativeTime] = useState("");
  const clientReady = useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getLatestSyncRun()
      .then((latest) => {
        setRun(latest);
        if (latest) {
          setRelativeTime(formatRelativeTime(latest.finishedAt ?? latest.startedAt));
        } else {
          setRelativeTime("");
        }
      })
      .catch(() => setError("Could not load sync status"))
      .finally(() => setLoading(false));
  }, [api]);

  useEffect(() => {
    if (backendOffline) return;
    let active = true;
    api
      .getLatestSyncRun()
      .then((latest) => {
        if (!active) return;
        setRun(latest);
        if (latest) {
          if (latest.status === "running") {
            setRelativeTime("Sync in progress…");
          } else {
            setRelativeTime(formatRelativeTime(latest.finishedAt ?? latest.startedAt));
          }
        }
      })
      .catch(() => {
        if (!active) return;
        setError("Could not load sync status");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, backendOffline]);

  const wrapper =
    variant === "sidebar"
      ? "rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2"
      : "text-sm";

  if (!clientReady) {
    return (
      <div className={wrapper} role="status" aria-busy="true">
        <p className="text-xs text-[var(--muted)]">Checking sync status…</p>
      </div>
    );
  }

  if (mode === "http" && checking) {
    return (
      <div className={wrapper} role="status" aria-busy="true">
        <p className="text-xs text-[var(--muted)]">Connecting to Hey Canvas service…</p>
      </div>
    );
  }

  if (backendOffline) {
    return (
      <div className={wrapper} role="status">
        <p className="text-xs text-[var(--muted)]">
          Local Hey Canvas service is offline. Start it on your computer to see Canvas sync status.
        </p>
        <Link
          href="/settings#connection"
          className="mt-2 inline-block text-xs text-[var(--accent)] underline"
        >
          Connection settings
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={wrapper} role="status" aria-busy="true">
        <p className="text-xs text-[var(--muted)]">Checking sync status…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={wrapper} role="status">
        <p className="text-xs text-[var(--muted)]">{error}</p>
        <button
          type="button"
          onClick={() => refresh()}
          className="mt-2 text-xs font-medium text-[var(--accent)] underline underline-offset-2"
        >
          Try again
        </button>
      </div>
    );
  }

  const recovery = syncStatusRecoveryHint(run);

  if (!run) {
    return (
      <div className={wrapper} role="status">
        <p className="text-xs text-[var(--muted)]">
          No Canvas sync recorded yet.
          {showDemoBadge
            ? " Course data may come from demo seed until Canvas sync runs."
            : " Run a Canvas sync on the backend to load your courses."}
        </p>
        {recovery ? <p className="mt-2 text-xs text-[var(--muted)]">{recovery}</p> : null}
        <button
          type="button"
          onClick={() => refresh()}
          className="mt-2 w-full rounded-md border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--surface)]"
        >
          Refresh status
        </button>
      </div>
    );
  }

  return (
    <div className={wrapper} role="status" aria-live="polite">
      <div className="flex items-start gap-2">
        <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${statusDot(run.status)}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-[var(--foreground)]">{statusLabel(run.status)}</p>
          <p className="text-xs text-[var(--muted)]" suppressHydrationWarning>
            {relativeTime || "…"}
            {run.changeEventsCreated > 0 ? ` · ${run.changeEventsCreated} changes` : ""}
          </p>
          {syncStatusIsUnhealthy(run.status) && recovery ? (
            <p className="mt-1 text-xs text-[var(--warn-text)]">{recovery}</p>
          ) : null}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => refresh()}
          className="flex-1 rounded-md border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--surface)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Refresh status
        </button>
        <Link
          href="/sync"
          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--accent)] hover:bg-[var(--surface)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          title="Open Sync manager"
        >
          History ↗
        </Link>
      </div>
    </div>
  );
}
