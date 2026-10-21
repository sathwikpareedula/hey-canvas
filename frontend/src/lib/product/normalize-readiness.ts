import type { ProductReadiness, ReadinessCheck } from "@/lib/domain/product-settings";
import type { SyncProbe } from "@/lib/product/synthesize-readiness";
import { sanitizeReadinessDetail } from "@/lib/product/readiness-copy";

function statusRank(status: ReadinessCheck["status"]): number {
  switch (status) {
    case "ready":
      return 5;
    case "degraded":
      return 4;
    case "action_required":
      return 3;
    case "unavailable":
      return 2;
    case "unknown":
      return 1;
    default:
      return 0;
  }
}

function preferReadinessCheck(a: ReadinessCheck, b: ReadinessCheck): ReadinessCheck {
  const rankA = statusRank(a.status);
  const rankB = statusRank(b.status);
  if (rankB > rankA) return b;
  if (rankA > rankB) return a;
  if (b.detail && !a.detail) return b;
  return a;
}

function dedupeChecks(checks: ReadinessCheck[]): ReadinessCheck[] {
  const byComponent = new Map<string, ReadinessCheck>();
  for (const check of checks) {
    const prev = byComponent.get(check.component);
    byComponent.set(check.component, prev ? preferReadinessCheck(prev, check) : check);
  }
  return [...byComponent.values()];
}

function enrichFromSyncProbe(check: ReadinessCheck, sync?: SyncProbe): ReadinessCheck {
  if (check.component !== "sync" || !sync?.hasSync) return check;
  if (check.status === "unknown" || !check.detail) {
    return {
      ...check,
      status: sync.status === "failed" ? "degraded" : "ready",
      detail: sync.relativeLabel ? `Last sync ${sync.relativeLabel}` : check.detail,
    };
  }
  return check;
}

function enrichCanvas(check: ReadinessCheck, backendOk?: boolean): ReadinessCheck {
  if (check.component !== "canvas") return check;
  if (check.status === "unknown") {
    return {
      ...check,
      status: backendOk ? "unknown" : "unavailable",
      detail:
        sanitizeReadinessDetail(check.detail) ??
        "Live Canvas has not been checked yet — synced data on this computer is still available.",
    };
  }
  return check;
}

export function normalizeProductReadiness(
  readiness: ProductReadiness,
  context?: { backendOk?: boolean; syncProbe?: SyncProbe },
): ProductReadiness {
  const checks = dedupeChecks(readiness.checks).map((c) => {
    let next = enrichFromSyncProbe(c, context?.syncProbe);
    next = enrichCanvas(next, context?.backendOk);
    if (next.status === "unknown" && !next.detail) {
      next = {
        ...next,
        detail: "Status not available from the service yet.",
      };
    }
    return next;
  });

  const overall =
    checks.some((c) => c.status === "unavailable")
      ? "unavailable"
      : checks.some((c) => c.status === "action_required")
        ? "action_required"
        : checks.some((c) => c.status === "degraded")
          ? "degraded"
          : checks.every((c) => c.status === "ready" || c.status === "unknown")
            ? readiness.overall
            : "ready";

  return { ...readiness, checks, overall };
}
