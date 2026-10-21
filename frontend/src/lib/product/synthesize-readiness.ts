import { fetchHealth } from "@/lib/api/http/fetch-json";
import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";
import type { ProductReadiness, ReadinessCheck } from "@/lib/domain/product-settings";
import { buildLocalAiSnapshot } from "@/lib/local-ai/build-snapshot";
import { mapLocalAiSnapshotToReadiness } from "@/lib/local-ai/readiness-bridge";
import { getApiMode } from "@/lib/api";
import { readAiPreferences } from "@/lib/product/ai-preferences";

export interface SyncProbe {
  hasSync: boolean;
  status?: string;
  relativeLabel?: string;
}

export async function synthesizeClientReadiness(options?: {
  backendOk?: boolean;
  sync?: SyncProbe;
  canvasOnline?: boolean;
}): Promise<ProductReadiness> {
  const base = resolveApiBaseUrl();
  const backendOk = options?.backendOk ?? (await fetchHealth(base));

  const checks: ReadinessCheck[] = [];

  checks.push({
    component: "backend",
    status: backendOk ? "ready" : "unavailable",
    label: "Service",
    detail: backendOk ? null : "Start Hey Canvas from the Windows launcher or your usual startup shortcut.",
    actionLabel: backendOk ? null : "Retry",
  });

  checks.push({
    component: "database",
    status: backendOk ? "ready" : "unavailable",
    label: "Database",
    detail: backendOk ? null : "The local database starts with the Hey Canvas service.",
    actionLabel: null,
  });

  const canvasOnline = options?.canvasOnline;
  checks.push({
    component: "canvas",
    status: canvasOnline === true ? "ready" : canvasOnline === false ? "degraded" : "unknown",
    label: "Canvas",
    detail:
      canvasOnline === true
        ? null
        : canvasOnline === false
          ? "Canvas connection unavailable — you can still use synced data on this computer."
          : "Live Canvas status has not been checked — synced data remains available.",
    actionLabel: null,
  });

  const sync = options?.sync;
  checks.push({
    component: "sync",
    status: !sync?.hasSync ? "action_required" : sync.status === "failed" ? "degraded" : "ready",
    label: "Sync",
    detail: sync?.relativeLabel
      ? `Last sync ${sync.relativeLabel}`
      : !sync?.hasSync
        ? "No sync recorded yet — connect Canvas on this computer."
        : null,
    actionLabel: null,
  });

  if (backendOk) {
    const mode = getApiMode();
    const aiMode = readAiPreferences().processingMode;
    const localAi = await buildLocalAiSnapshot({
      mode,
      probeRuntime: mode === "http" && aiMode === "local",
    });
    checks.push(...mapLocalAiSnapshotToReadiness(localAi, aiMode));
  }

  const overall =
    checks.some((c) => c.status === "unavailable")
      ? "unavailable"
      : checks.some((c) => c.status === "action_required")
        ? "action_required"
        : checks.some((c) => c.status === "degraded")
          ? "degraded"
          : "ready";

  return {
    overall,
    checks,
    updatedAt: new Date().toISOString(),
  };
}
