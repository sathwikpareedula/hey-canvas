"use client";

import Link from "next/link";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import type { ReadinessCheck, ReadinessStatus } from "@/lib/domain/product-settings";
import {
  readinessCheckStudentLabel,
  readinessStatusStudentLine,
  sanitizeReadinessDetail,
} from "@/lib/product/readiness-copy";

function tone(status: ReadinessStatus): string {
  switch (status) {
    case "ready":
      return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
    case "degraded":
      return "bg-amber-500/15 text-amber-900 dark:text-amber-100";
    case "action_required":
    case "unavailable":
      return "bg-red-500/15 text-red-900 dark:text-red-100";
    default:
      return "bg-[var(--surface-muted)] text-[var(--muted)]";
  }
}

function CheckRow({ check }: { check: ReadinessCheck }) {
  return (
    <li className="flex items-start gap-2 rounded-lg border border-[var(--border)] px-3 py-2">
      <span
        className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${check.status === "ready" ? "bg-emerald-500" : check.status === "degraded" ? "bg-amber-500" : "bg-[var(--muted)]"}`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{readinessCheckStudentLabel(check.component)}</p>
        <p className="text-xs text-[var(--muted)]">
          {readinessStatusStudentLine(
            check.component,
            check.status,
            sanitizeReadinessDetail(check.detail),
          )}
        </p>
      </div>
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${tone(check.status)}`}>
        {check.status.replace("_", " ")}
      </span>
    </li>
  );
}

export function ReadinessPanel({ compact }: { compact?: boolean }) {
  const { readiness, loading, source } = useProductSettings();

  if (loading) {
    return (
      <p className="text-sm text-[var(--muted)]" role="status">Checking readiness…</p>
    );
  }

  if (!readiness?.checks.length) {
    return (
      <div className="space-y-2 text-sm text-[var(--muted)]" role="status">
        <p>Readiness details will appear when your local Hey Canvas service provides them.</p>
        <p className="text-xs">
          Settings source: <span className="font-medium text-[var(--foreground)]">{source ?? "unknown"}</span>
        </p>
        <Link href="/settings#connection" className="text-[var(--accent)] underline">
          Check connection
        </Link>
      </div>
    );
  }

  return (
    <div className={compact ? "space-y-2" : "space-y-3"} role="status" aria-live="polite">
      {!compact ? (
        <p className="text-xs text-[var(--muted)]">
          Overall:{" "}
          <span className="font-medium text-[var(--foreground)]">
            {readiness.overall.replace("_", " ")}
          </span>
        </p>
      ) : null}
      <ul className="space-y-2">
        {readiness.checks.map((c) => (
          <CheckRow key={c.component} check={c} />
        ))}
      </ul>
    </div>
  );
}
