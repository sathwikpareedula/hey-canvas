"use client";

import { useCallback, useEffect, useState } from "react";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import {
  fetchSecurityHealthSnapshot,
  migrateCanvasTokenToSecureStore,
  runSecurityHealthChecks,
  type SecurityCheck,
  type SecurityHealthReport,
} from "@/lib/api/http/security-health-api";

const STATUS_LABEL: Record<SecurityCheck["status"], string> = {
  pass: "Pass",
  warning: "Warning",
  fail: "Fail",
  not_checked: "Not checked",
};

const STATUS_CLASS: Record<SecurityCheck["status"], string> = {
  pass: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  fail: "text-red-600 dark:text-red-400",
  not_checked: "text-[var(--muted)]",
};

function CheckRow({ check }: { check: SecurityCheck }) {
  return (
    <li className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-[var(--foreground)]">{check.title}</p>
        <span className={`text-xs font-semibold uppercase tracking-wide ${STATUS_CLASS[check.status]}`}>
          {STATUS_LABEL[check.status]}
        </span>
      </div>
      <p className="mt-1 text-sm text-[var(--muted)]">{check.summary}</p>
      {check.detail ? (
        <p className="mt-1 text-xs text-[var(--muted)]">{check.detail}</p>
      ) : null}
    </li>
  );
}

export function SecurityHealthCenter() {
  const { mode, connection } = useBackendStatus();
  const [report, setReport] = useState<SecurityHealthReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secureMsg, setSecureMsg] = useState<string | null>(null);

  const loadSnapshot = useCallback(async () => {
    if (mode !== "http" || connection !== "connected") return;
    setError(null);
    try {
      const snap = await fetchSecurityHealthSnapshot();
      setReport(snap);
    } catch {
      setError("Could not load security checks. Confirm the academic service is running.");
    }
  }, [connection, mode]);

  useEffect(() => {
    if (mode !== "http" || connection !== "connected") return;
    let cancelled = false;
    fetchSecurityHealthSnapshot()
      .then((snap) => {
        if (!cancelled) setReport(snap);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Could not load security checks. Confirm the academic service is running.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [connection, mode]);

  const runChecks = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await runSecurityHealthChecks();
      setReport(result);
    } catch {
      setError("Security checks could not finish. Try again in a moment.");
    } finally {
      setLoading(false);
    }
  };

  const secureStore = async () => {
    setSecureMsg(null);
    try {
      const result = await migrateCanvasTokenToSecureStore();
      setSecureMsg(result.message);
      await loadSnapshot();
    } catch {
      setSecureMsg("Could not move your token to secure storage.");
    }
  };

  if (mode !== "http") {
    return (
      <p className="text-sm text-[var(--muted)]">
        Security checks apply when Hey Canvas is connected to your local academic service.
      </p>
    );
  }

  if (connection !== "connected") {
    return (
      <p className="text-sm text-[var(--muted)]">
        Start the academic service on your computer to run security and health checks.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--muted)]">
        These checks verify how Hey Canvas protects your Canvas token, keeps services on your
        computer, and keeps course data isolated. Nothing here shows secrets or file paths.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void runChecks()}
          disabled={loading}
          className="min-h-10 rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Running checks…" : "Run checks"}
        </button>
        <button
          type="button"
          onClick={() => void secureStore()}
          className="min-h-10 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm"
        >
          Move token to Windows secure storage
        </button>
      </div>
      {secureMsg ? (
        <p className="text-xs text-[var(--muted)]" role="status">{secureMsg}</p>
      ) : null}
      {error ? <p className="text-sm text-[var(--warn-text)]" role="alert">{error}</p> : null}
      {report ? (
        <ul className="space-y-2" aria-live="polite">
          {report.checks.map((check) => (
            <CheckRow key={check.id} check={check} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-[var(--muted)]">Loading snapshot…</p>
      )}
    </div>
  );
}
