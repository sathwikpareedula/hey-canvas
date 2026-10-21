import {
  fetchAssistantRuntimeStatus,
  type AssistantRuntimeStatus,
} from "@/lib/api/http/assistant-status";
import {
  fetchInstalledLocalModels,
  fetchSystemReadiness,
  runOllamaBenchmark,
} from "@/lib/api/http/local-ai-client";
import { isExplicitDemoMode } from "@/lib/api/app-mode";
import type { LocalAiSnapshot, LocalAiRuntimeStatus } from "@/lib/domain/local-ai";
import { DEFAULT_BENCHMARK_CASES } from "@/lib/domain/local-ai";
import {
  runtimeStatusDetail,
  runtimeStatusHeadline,
  sanitizeLocalAiDetail,
} from "@/lib/local-ai/student-messages";

export interface BuildLocalAiSnapshotOptions {
  mode: "mock" | "http";
  /** Light reachability via assistant status + installed models (startup/readiness). */
  probeRuntime?: boolean;
  /** Expensive inference probe — Local AI settings/diagnostics only. */
  probeWithBenchmark?: boolean;
}

export function resolveInstalledModelMatch(
  selected: string | null,
  installed: string[],
): string | null {
  if (!selected) return null;
  if (installed.includes(selected)) return selected;
  const exactTag = installed.find(
    (m) => m === selected || m.startsWith(`${selected}:`) || m.startsWith(`${selected}@`),
  );
  if (exactTag) return exactTag;
  const fuzzy = installed.find((m) => m.split(":")[0] === selected.split(":")[0]);
  return fuzzy ?? selected;
}

function inferSelectedModel(
  readiness: Awaited<ReturnType<typeof fetchSystemReadiness>>,
): string | null {
  const detail = readiness?.local_model?.detail;
  if (detail && detail !== "synthetic" && !detail.includes("provider")) {
    const safe = sanitizeLocalAiDetail(detail);
    if (safe) return safe;
  }
  return null;
}

function mapRuntimeStatus(
  mode: "mock" | "http",
  assistant: AssistantRuntimeStatus | null,
  selectedModel: string | null,
  installed: string[],
): LocalAiRuntimeStatus {
  if (!assistant) return "unknown";
  if (assistant.provider === "synthetic") {
    return mode === "mock" || isExplicitDemoMode() ? "demo" : "not_installed";
  }
  if (!assistant.configured) return "not_installed";
  if (assistant.available === false) return "not_running";
  if (!installed.length && !selectedModel) return "needs_model";
  if (selectedModel && installed.length && !installed.includes(selectedModel)) {
    return "selected_missing";
  }
  if (assistant.available === true || (assistant.available === null && selectedModel)) {
    return "ready";
  }
  return "unknown";
}

export async function buildLocalAiSnapshot(
  options: BuildLocalAiSnapshotOptions,
): Promise<LocalAiSnapshot> {
  if (options.mode === "mock") {
    return {
      runtimeStatus: "demo",
      statusHeadline: runtimeStatusHeadline("demo"),
      statusDetail: runtimeStatusDetail("demo"),
      selectedModel: "demo-model",
      installedModels: ["demo-model", "demo-model-fast"],
      installedModelsSource: "backend",
      provider: "synthetic",
      assistantConfigured: true,
      discoverySupported: true,
      selectionSupported: true,
      benchmarkSupported: true,
      updatedAt: new Date().toISOString(),
    };
  }

  const [assistant, readiness, installed] = await Promise.all([
    fetchAssistantRuntimeStatus(),
    fetchSystemReadiness(),
    fetchInstalledLocalModels(),
  ]);

  let installedModels = installed.models;
  let installedModelsSource: LocalAiSnapshot["installedModelsSource"] = installed.supported
    ? "backend"
    : "none";
  const selectedModel = resolveInstalledModelMatch(
    inferSelectedModel(readiness),
    installedModels,
  );

  if (!installedModels.length && selectedModel) {
    installedModels = [selectedModel];
    installedModelsSource = "inferred" as const;
  }

  let runtimeStatus = mapRuntimeStatus(options.mode, assistant, selectedModel, installedModels);

  if (
    options.probeRuntime &&
    runtimeStatus !== "demo" &&
    selectedModel &&
    runtimeStatus !== "not_installed"
  ) {
    if (assistant?.available === false) {
      runtimeStatus = "not_running";
    } else if (installedModels.length && selectedModel && !installedModels.includes(selectedModel)) {
      runtimeStatus = "selected_missing";
    } else if (assistant?.available === true || (installedModels.length > 0 && selectedModel)) {
      runtimeStatus = "ready";
    }
  }

  if (
    options.probeWithBenchmark &&
    runtimeStatus !== "demo" &&
    selectedModel &&
    runtimeStatus !== "not_installed"
  ) {
    try {
      const probe = await runOllamaBenchmark([selectedModel], [DEFAULT_BENCHMARK_CASES[0]]);
      const row = probe[0];
      if (row?.error === "model_not_installed") {
        runtimeStatus = "selected_missing";
      } else if (!row?.success && row?.error?.toLowerCase().includes("timeout")) {
        runtimeStatus = "not_running";
      } else if (!row?.success && row?.error) {
        runtimeStatus = "error";
      } else if (row?.success) {
        runtimeStatus = "ready";
      }
    } catch {
      runtimeStatus = runtimeStatus === "ready" ? "not_running" : runtimeStatus;
    }
  }

  return {
    runtimeStatus,
    statusHeadline: runtimeStatusHeadline(runtimeStatus),
    statusDetail:
      sanitizeLocalAiDetail(readiness?.local_runtime?.detail) ?? runtimeStatusDetail(runtimeStatus),
    selectedModel,
    installedModels,
    installedModelsSource,
    provider: assistant?.provider ?? null,
    assistantConfigured: Boolean(assistant?.configured),
    discoverySupported: installed.supported,
    selectionSupported: false,
    benchmarkSupported: true,
    updatedAt: new Date().toISOString(),
  };
}
