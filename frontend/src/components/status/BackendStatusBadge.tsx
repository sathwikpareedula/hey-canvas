"use client";

import Link from "next/link";
import { useBackendStatus } from "@/contexts/BackendStatusContext";

function label(connection: string, mode: string, checking: boolean): string {
  if (checking) return "Checking API…";
  if (mode === "mock") return "Mock data";
  if (connection === "connected") return "Backend connected";
  return "Backend unavailable";
}

export function BackendStatusBadge({ compact }: { compact?: boolean }) {
  const { mode, connection, checking } = useBackendStatus();
  const dot =
    mode === "mock"
      ? "bg-[var(--muted)]"
      : connection === "connected"
        ? "bg-emerald-500"
        : "bg-red-500";

  const showRecovery = mode === "http" && connection !== "connected" && !checking;

  return (
    <span
      className={`inline-flex flex-wrap items-center gap-1.5 text-xs text-[var(--muted)] ${compact ? "" : "rounded-md border border-[var(--border)] px-2 py-1"}`}
      role="status"
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
      {label(connection, mode, checking)}
      {showRecovery ? (
        <Link href="/settings#connection" className="text-[var(--accent)] underline">
          Fix connection
        </Link>
      ) : null}
    </span>
  );
}
