"use client";

import Link from "next/link";
import { useBackendStatus } from "@/contexts/BackendStatusContext";

export function StartupGuidanceBanner() {
  const { mode, connection, checking } = useBackendStatus();

  if (checking) return null;
  if (mode === "mock") {
    return (
      <div
        className="border-b border-[var(--border)] bg-[var(--surface-muted)] px-4 py-2 text-center text-xs text-[var(--muted)] md:px-8"
        role="status"
      >
        Demo mode — synthetic courses only. No real Canvas data is used.
      </div>
    );
  }
  if (connection === "connected") return null;

  return (
    <div
      className="border-b border-[var(--warn-border)] bg-[var(--warn-bg)] px-4 py-2 text-sm text-[var(--warn-text)] md:px-8"
      role="status"
    >
      Hey Canvas cannot reach your local academic service. Open Hey Canvas from your installed app
      or start the local backend on this computer, then{" "}
      <Link href="/settings#connection" className="font-medium underline">
        check connection
      </Link>
      .
    </div>
  );
}
