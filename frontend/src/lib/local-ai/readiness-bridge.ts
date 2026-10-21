import type { LocalAiSnapshot } from "@/lib/domain/local-ai";
import type { ReadinessCheck } from "@/lib/domain/product-settings";
import { sanitizeLocalAiDetail } from "@/lib/local-ai/student-messages";

export function mapLocalAiSnapshotToReadiness(
  snapshot: LocalAiSnapshot,
  aiProcessingMode: "local" | "cloud",
): ReadinessCheck[] {
  if (aiProcessingMode === "cloud") {
    return [
      {
        component: "privacy",
        status: "ready",
        label: "Cloud AI",
        detail: "Optional cloud processing is enabled in settings.",
        actionLabel: null,
      },
    ];
  }

  if (snapshot.runtimeStatus === "demo") {
    return [
      {
        component: "local_ai_runtime",
        status: "ready",
        label: "Local AI",
        detail: snapshot.statusDetail,
        actionLabel: null,
      },
    ];
  }

  const runtimeStatus =
    snapshot.runtimeStatus === "ready"
      ? "ready"
      : snapshot.runtimeStatus === "not_running" || snapshot.runtimeStatus === "error"
        ? "unavailable"
        : "action_required";

  const modelStatus: ReadinessCheck["status"] =
    snapshot.runtimeStatus === "ready"
      ? "ready"
      : snapshot.runtimeStatus === "selected_missing" || snapshot.runtimeStatus === "needs_model"
        ? "action_required"
        : snapshot.runtimeStatus === "not_running" || snapshot.runtimeStatus === "error"
          ? "unavailable"
          : "unknown";

  const modelDetail =
    snapshot.selectedModel
      ? `Selected: ${snapshot.selectedModel}`
      : snapshot.runtimeStatus === "needs_model"
        ? "Install a model for Local AI."
        : null;

  return [
    {
      component: "local_ai_runtime",
      status: runtimeStatus,
      label: "Local AI",
      detail: sanitizeLocalAiDetail(snapshot.statusDetail) ?? snapshot.statusHeadline,
      actionLabel: runtimeStatus === "action_required" ? "Set up Local AI" : null,
    },
    {
      component: "local_ai_model",
      status: modelStatus as ReadinessCheck["status"],
      label: "AI model",
      detail: sanitizeLocalAiDetail(modelDetail),
      actionLabel: modelStatus === "action_required" ? "Choose model" : null,
    },
  ];
}
