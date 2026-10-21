"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import { getProductSettingsApi, loadReadiness } from "@/lib/api/product-settings-service";
import type { ProductReadiness } from "@/lib/domain/product-settings";
import { buildLocalAiSnapshot } from "@/lib/local-ai/build-snapshot";
import {
  readinessCheckStudentLabel,
  readinessStatusStudentLine,
} from "@/lib/product/readiness-copy";
import { formatRelativeTime } from "@/lib/utils/date";
import { probeBackendConnection } from "@/lib/api/backend-probe";
import { localAiBlocksStartup } from "@/lib/product/startup-gates";

function useIsClient(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

const MAX_POLL_ATTEMPTS = 40;
const FAST_POLL_MS = 3000;
const SLOW_POLL_MS = 8000;

export function StartupExperience() {
  const router = useRouter();
  const api = useAcademicApi();
  const { mode } = useBackendStatus();
  const { settings } = useProductSettings();
  const aiMode = settings?.aiProcessingMode ?? "local";
  const [readiness, setReadiness] = useState<ProductReadiness | null>(null);
  const [headline, setHeadline] = useState("Starting Hey Canvas…");
  const [localAiHeadline, setLocalAiHeadline] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stalled, setStalled] = useState(false);
  const clientReady = useIsClient();
  const attemptsRef = useRef(0);

  const poll = useCallback(async () => {
    setError(null);
    attemptsRef.current += 1;
    if (attemptsRef.current >= MAX_POLL_ATTEMPTS) {
      setStalled(true);
    }
    const backendOk =
      mode === "mock" ? true : (await probeBackendConnection()) === "connected";
    let syncProbe = { hasSync: false as boolean, relativeLabel: undefined as string | undefined };
    if (backendOk) {
      try {
        const run = await api.getLatestSyncRun();
        if (run) {
          syncProbe = {
            hasSync: true,
            relativeLabel: formatRelativeTime(run.finishedAt ?? run.startedAt),
          };
        }
      } catch {
        /* optional */
      }
    }
    const ready = await loadReadiness(getProductSettingsApi(), {
      backendOk,
      syncProbe,
    });
    setReadiness(ready);

    if (backendOk && mode !== "mock") {
      const localSnap = await buildLocalAiSnapshot({ mode, probeRuntime: aiMode === "local" });
      setLocalAiHeadline(localSnap.statusHeadline);
    } else {
      setLocalAiHeadline(null);
    }

    if (mode === "mock") {
      setHeadline("Ready");
      router.replace("/dashboard");
      return;
    }
    if (!backendOk) {
      setHeadline("Waiting for Hey Canvas service…");
      return;
    }

    const canEnter =
      (ready.overall === "ready" || ready.overall === "degraded") &&
      !localAiBlocksStartup(ready, aiMode);

    if (canEnter) {
      setHeadline("Ready");
      router.replace("/dashboard");
      return;
    }

    if (localAiBlocksStartup(ready, aiMode)) {
      setHeadline("Checking Local AI…");
      return;
    }
    if (ready.overall === "action_required") {
      setHeadline("Almost ready — a few setup steps remain");
    } else {
      setHeadline("Starting Hey Canvas…");
    }
  }, [api, mode, router, aiMode]);

  useEffect(() => {
    let intervalMs = FAST_POLL_MS;
    const tick = () => void poll();
    const first = window.setTimeout(tick, 0);
    let intervalId = window.setInterval(tick, intervalMs);
    const slowTimer = window.setTimeout(() => {
      window.clearInterval(intervalId);
      intervalMs = SLOW_POLL_MS;
      intervalId = window.setInterval(tick, intervalMs);
    }, 45_000);
    return () => {
      window.clearTimeout(first);
      window.clearTimeout(slowTimer);
      window.clearInterval(intervalId);
    };
  }, [poll]);

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight" suppressHydrationWarning>
        Hey Canvas
      </h1>
      <p
        className="mt-2 text-sm text-[var(--muted)]"
        role="status"
        aria-live="polite"
        suppressHydrationWarning
      >
        {clientReady ? headline : "Starting Hey Canvas…"}
      </p>
      {clientReady && localAiHeadline ? (
        <p className="mt-1 text-sm text-[var(--foreground)]" role="status" suppressHydrationWarning>
          {localAiHeadline}
        </p>
      ) : null}
      {stalled ? (
        <p className="mt-2 text-xs text-[var(--warn-text)]" role="status">
          Setup is taking longer than expected. You can retry, open Local AI settings, or continue
          anyway.
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 text-sm text-[var(--warn-text)]" role="alert">{error}</p>
      ) : null}
      <ul className="mt-8 space-y-3" suppressHydrationWarning>
        {!clientReady ? (
          <li className="text-sm text-[var(--muted)]" role="status">Checking your data…</li>
        ) : null}
        {clientReady
          ? (readiness?.checks ?? []).map((check) => (
          <li
            key={check.component}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          >
            <p className="font-medium">{readinessCheckStudentLabel(check.component)}</p>
            <p className="text-xs text-[var(--muted)]">
              {readinessStatusStudentLine(check.component, check.status, check.detail)}
            </p>
          </li>
            ))
          : null}
        {clientReady && !readiness?.checks.length ? (
          <li className="text-sm text-[var(--muted)]" role="status">Checking your data…</li>
        ) : null}
      </ul>
      <div className="mt-8 flex flex-wrap gap-3 text-sm">
        <button
          type="button"
          onClick={() => {
            attemptsRef.current = 0;
            setStalled(false);
            void poll();
          }}
          className="rounded-lg border border-[var(--border)] px-4 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Retry
        </button>
        <Link href="/" className="rounded-lg text-[var(--accent)] underline">
          Open app anyway
        </Link>
        <Link href="/settings#local-ai" className="text-[var(--muted)] underline">
          Local AI settings
        </Link>
      </div>
      <p className="mt-10 text-xs text-[var(--muted)]">
        Tip: on Windows, use the Hey Canvas desktop shortcut or your saved Start command for daily
        launch.
      </p>
    </main>
  );
}
