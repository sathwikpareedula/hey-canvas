import type { ReadinessCheck, ReadinessStatus } from "@/lib/domain/product-settings";

const INTERNAL_PATTERN =
  /(traceback|exception|\/users\/|\.env|token|sqlite|ollama:\/\/|127\.0\.0\.1|localhost:\d+)/i;

export function sanitizeReadinessDetail(detail: string | null): string | null {
  if (!detail?.trim()) return null;
  if (INTERNAL_PATTERN.test(detail)) return null;
  return detail.trim();
}

export function readinessCheckStudentLabel(component: ReadinessCheck["component"]): string {
  switch (component) {
    case "backend":
      return "Hey Canvas service";
    case "database":
      return "Local database";
    case "canvas":
      return "Canvas connection";
    case "sync":
      return "Course sync";
    case "local_ai_runtime":
      return "Local AI runtime";
    case "local_ai_model":
      return "Local AI model";
    case "document_index":
      return "Course materials";
    case "privacy":
      return "Privacy mode";
    default:
      return "System";
  }
}

export function readinessStatusStudentLine(
  component: ReadinessCheck["component"],
  status: ReadinessStatus,
  detail?: string | null,
): string {
  const safeDetail = sanitizeReadinessDetail(detail ?? null);
  switch (component) {
    case "backend":
      if (status === "ready") return "Hey Canvas service is running.";
      if (status === "action_required") return "Hey Canvas service is not running yet.";
      return safeDetail ?? "Checking Hey Canvas service…";
    case "database":
      if (status === "ready") return "Local database is ready.";
      if (status === "unavailable") return "Local database could not start. Try restarting Hey Canvas.";
      if (status === "unknown") return safeDetail ?? "Local database status is not available yet.";
      return safeDetail ?? "Checking local database…";
    case "canvas":
      if (status === "ready") return "Canvas is connected.";
      if (status === "degraded") return "Canvas is unavailable — using synced data on this computer.";
      if (status === "unknown") {
        return (
          safeDetail ??
          "Live Canvas status is unknown — you can still use synced data on this computer."
        );
      }
      return safeDetail ?? "Checking Canvas connection…";
    case "sync":
      if (status === "ready") return "Your courses are synced locally.";
      if (status === "degraded") return "Sync may be out of date. You can still browse synced data.";
      if (status === "unknown") return safeDetail ?? "Last sync time is not available yet.";
      return safeDetail ?? "Checking last sync…";
    case "local_ai_runtime":
      if (status === "ready") return "Local AI runtime is ready.";
      if (status === "unavailable") return "Local AI runtime is not running.";
      return safeDetail ?? "Checking local AI…";
    case "local_ai_model":
      if (status === "ready") return "Your selected model is available.";
      if (status === "action_required") return "The selected model is not installed yet.";
      return safeDetail ?? "Checking model…";
    case "document_index":
      if (status === "ready") return "Materials are ready for questions.";
      if (status === "degraded") return "Some materials are still preparing.";
      return safeDetail ?? "Checking materials…";
    case "privacy":
      if (status === "ready") return "Processing stays on this computer (local mode).";
      return safeDetail ?? "Checking privacy settings…";
    default:
      return safeDetail ?? "Checking…";
  }
}

export function mapAssistantStatusToReadiness(
  configured: boolean,
  provider: string,
  available: boolean | null,
): ReadinessCheck[] {
  const checks: ReadinessCheck[] = [];
  if (provider === "synthetic") {
    checks.push({
      component: "local_ai_runtime",
      status: "ready",
      label: "Demo assistant",
      detail: "Synthetic demo data — not your real Canvas account.",
      actionLabel: null,
    });
    return checks;
  }
  if (!configured) {
    checks.push({
      component: "local_ai_runtime",
      status: "action_required",
      label: "Local AI",
      detail: "Local AI is not configured on this computer yet.",
      actionLabel: "Open Settings",
    });
    return checks;
  }
  if (available === false) {
    checks.push({
      component: "local_ai_runtime",
      status: "unavailable",
      label: "Local AI",
      detail: "Local AI is installed but not running. Start it, then try again.",
      actionLabel: "Open Local AI settings",
    });
    checks.push({
      component: "local_ai_model",
      status: "action_required",
      label: "Model",
      detail: "Install a model for Local AI (Hey Canvas will not download one automatically).",
      actionLabel: null,
    });
  } else {
    checks.push({
      component: "local_ai_runtime",
      status: "ready",
      label: "Local AI",
      detail: "Local AI is ready.",
      actionLabel: null,
    });
    checks.push({
      component: "local_ai_model",
      status: available === null ? "degraded" : "ready",
      label: "Model",
      detail: available === null ? "Model status unknown — answers may still work." : "Model is available.",
      actionLabel: null,
    });
  }
  return checks;
}
