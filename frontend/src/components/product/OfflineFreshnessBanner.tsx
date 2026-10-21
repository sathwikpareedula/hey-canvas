"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { formatRelativeTime } from "@/lib/utils/date";

export function OfflineFreshnessBanner() {
  const api = useAcademicApi();
  const { mode, connection, checking } = useBackendStatus();
  const [lastSync, setLastSync] = useState<string | null>(null);

  useEffect(() => {
    if (mode === "mock") return;
    let active = true;
    api
      .getLatestSyncRun()
      .then((run) => {
        if (!active || !run) return;
        setLastSync(formatRelativeTime(run.finishedAt ?? run.startedAt));
      })
      .catch(() => {
        if (active) setLastSync(null);
      });
    return () => {
      active = false;
    };
  }, [api, mode]);

  if (mode === "mock") return null;
  if (checking) return null;

  if (connection !== "connected") {
    return (
      <div
        className="border-b border-[var(--warn-border)] bg-[var(--warn-bg)] px-4 py-2 text-center text-xs text-[var(--warn-text)] md:px-8"
        role="status"
      >
        Using synced Canvas data on this computer.
        {lastSync ? ` Last synced ${lastSync}.` : ""}
        Canvas live connection is unavailable.
        <Link href="/settings#connection" className="ml-1 underline">Check connection</Link>
      </div>
    );
  }

  if (lastSync) {
    return (
      <div
        className="hidden border-b border-[var(--border)] bg-[var(--surface-muted)] px-4 py-1 text-center text-[10px] text-[var(--muted)] md:block md:px-8"
        role="status"
      >
        Synced Canvas data · last sync {lastSync}
      </div>
    );
  }

  return null;
}
