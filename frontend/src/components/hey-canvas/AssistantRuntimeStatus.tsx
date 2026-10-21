"use client";

import { useEffect, useState } from "react";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import {
  describeAssistantRuntimeStatus,
  fetchAssistantRuntimeStatus,
  type AssistantRuntimeStatus,
} from "@/lib/api/http/assistant-status";

export function AssistantRuntimeStatus() {
  const { mode, connection } = useBackendStatus();
  const shouldFetch = mode === "http" && connection === "connected";
  const [status, setStatus] = useState<AssistantRuntimeStatus | null>(null);

  useEffect(() => {
    if (!shouldFetch) return;
    let active = true;
    const tick = () => {
      fetchAssistantRuntimeStatus().then((s) => {
        if (active) setStatus(s);
      });
    };
    tick();
    const interval = window.setInterval(tick, 15_000);
    const onFocus = () => tick();
    window.addEventListener("focus", onFocus);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [shouldFetch]);

  if (mode === "mock") {
    return (
      <p className="text-xs text-[var(--muted)]" role="status">
        Mock academic data — assistant uses local sample transport.
      </p>
    );
  }

  if (connection !== "connected") {
    return (
      <p className="text-xs text-[var(--warn-text)]" role="status">
        Backend unreachable — Hey Canvas cannot reach the academic API.
      </p>
    );
  }

  return (
    <p className="text-xs text-[var(--muted)]" role="status" aria-live="polite">
      {describeAssistantRuntimeStatus(shouldFetch ? status : null)}
    </p>
  );
}
