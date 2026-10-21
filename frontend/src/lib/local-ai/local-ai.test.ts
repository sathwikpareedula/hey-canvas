/**
 * @vitest-environment node
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { mapLocalAiSnapshotToReadiness } from "@/lib/local-ai/readiness-bridge";
import { pickRecommendedModelFromBenchmarks } from "@/lib/local-ai/pick-recommendation";
import { sanitizeLocalAiDetail, benchmarkErrorLabel } from "@/lib/local-ai/student-messages";
import type { LocalAiSnapshot, BenchmarkResult } from "@/lib/domain/local-ai";
import { buildLocalAiSnapshot } from "@/lib/local-ai/build-snapshot";
import * as assistantStatus from "@/lib/api/http/assistant-status";
import * as localAiClient from "@/lib/api/http/local-ai-client";

function snap(partial: Partial<LocalAiSnapshot>): LocalAiSnapshot {
  return {
    runtimeStatus: "unknown",
    statusHeadline: "Checking",
    statusDetail: null,
    selectedModel: null,
    installedModels: [],
    installedModelsSource: "none",
    provider: null,
    assistantConfigured: false,
    discoverySupported: false,
    selectionSupported: false,
    benchmarkSupported: true,
    updatedAt: new Date().toISOString(),
    ...partial,
  };
}

describe("sanitizeLocalAiDetail", () => {
  it("strips internal host references", () => {
    expect(sanitizeLocalAiDetail("failed at http://127.0.0.1:11434")).toBeNull();
    expect(sanitizeLocalAiDetail("Model llama ready")).toBe("Model llama ready");
  });
});

describe("benchmarkErrorLabel", () => {
  it("maps model_not_installed", () => {
    expect(benchmarkErrorLabel("model_not_installed")).toMatch(/not installed/i);
  });
  it("maps timeout", () => {
    expect(benchmarkErrorLabel("timeout")).toMatch(/timed out/i);
  });
});

describe("mapLocalAiSnapshotToReadiness", () => {
  it("cloud mode does not block on local runtime", () => {
    const checks = mapLocalAiSnapshotToReadiness(
      snap({ runtimeStatus: "not_running" }),
      "cloud",
    );
    expect(checks[0].component).toBe("privacy");
  });

  it("local ready maps runtime and model", () => {
    const checks = mapLocalAiSnapshotToReadiness(
      snap({
        runtimeStatus: "ready",
        selectedModel: "alpha:7b",
        installedModels: ["alpha:7b"],
      }),
      "local",
    );
    expect(checks.find((c) => c.component === "local_ai_runtime")?.status).toBe("ready");
    expect(checks.find((c) => c.component === "local_ai_model")?.detail).toMatch(/alpha:7b/);
  });

  it("missing model is action_required", () => {
    const checks = mapLocalAiSnapshotToReadiness(
      snap({ runtimeStatus: "needs_model", installedModels: [] }),
      "local",
    );
    expect(checks.find((c) => c.component === "local_ai_model")?.status).toBe("action_required");
  });

  it("selected missing model", () => {
    const checks = mapLocalAiSnapshotToReadiness(
      snap({
        runtimeStatus: "selected_missing",
        selectedModel: "gone:1b",
        installedModels: ["other:3b"],
      }),
      "local",
    );
    expect(checks.find((c) => c.component === "local_ai_model")?.status).toBe("action_required");
  });
});

describe("pickRecommendedModelFromBenchmarks", () => {
  it("picks faster successful model", () => {
    const rows: BenchmarkResult[] = [
      {
        case_id: "structured_json",
        provider: "ollama",
        model: "slow",
        success: true,
        timed_out: false,
        first_token_ms: 100,
        total_ms: 5000,
        structured_output_valid: true,
        output: "{}",
      },
      {
        case_id: "structured_json",
        provider: "ollama",
        model: "fast",
        success: true,
        timed_out: false,
        first_token_ms: 50,
        total_ms: 800,
        structured_output_valid: true,
        output: "{}",
      },
    ];
    expect(pickRecommendedModelFromBenchmarks(rows)).toBe("fast");
  });

  it("recommends model with partial benchmark success", () => {
    const rows: BenchmarkResult[] = [
      {
        case_id: "a",
        provider: "ollama",
        model: "mixed",
        success: true,
        timed_out: false,
        first_token_ms: 10,
        total_ms: 400,
        structured_output_valid: false,
        output: "ok",
      },
      {
        case_id: "b",
        provider: "ollama",
        model: "mixed",
        success: false,
        timed_out: true,
        first_token_ms: null,
        total_ms: 100,
        structured_output_valid: false,
        output: "",
        error: "timeout",
      },
      {
        case_id: "c",
        provider: "ollama",
        model: "broken",
        success: false,
        timed_out: true,
        first_token_ms: null,
        total_ms: 100,
        structured_output_valid: false,
        output: "",
        error: "timeout",
      },
    ];
    expect(pickRecommendedModelFromBenchmarks(rows)).toBe("mixed");
  });

  it("does not recommend when all fail", () => {
    expect(
      pickRecommendedModelFromBenchmarks([
        {
          case_id: "x",
          provider: "ollama",
          model: "a",
          success: false,
          timed_out: true,
          first_token_ms: null,
          total_ms: 100,
          structured_output_valid: false,
          output: "",
          error: "timeout",
        },
      ]),
    ).toBeNull();
  });
});

describe("buildLocalAiSnapshot", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("mock mode returns demo snapshot", async () => {
    const s = await buildLocalAiSnapshot({ mode: "mock" });
    expect(s.runtimeStatus).toBe("demo");
    expect(s.installedModels.length).toBeGreaterThan(0);
  });

  it("http not configured", async () => {
    vi.spyOn(assistantStatus, "fetchAssistantRuntimeStatus").mockResolvedValue({
      configured: false,
      provider: "ollama",
      available: false,
    });
    vi.spyOn(localAiClient, "fetchSystemReadiness").mockResolvedValue(null);
    vi.spyOn(localAiClient, "fetchInstalledLocalModels").mockResolvedValue({
      models: [],
      supported: false,
      available: null,
    });
    const s = await buildLocalAiSnapshot({ mode: "http" });
    expect(s.runtimeStatus).toBe("not_installed");
  });

  it("probe marks selected model missing", async () => {
    vi.spyOn(assistantStatus, "fetchAssistantRuntimeStatus").mockResolvedValue({
      configured: true,
      provider: "ollama",
      available: true,
    });
    vi.spyOn(localAiClient, "fetchSystemReadiness").mockResolvedValue({
      local_model: { status: "configured", detail: "ghost:1b" },
    });
    vi.spyOn(localAiClient, "fetchInstalledLocalModels").mockResolvedValue({
      models: ["real:3b"],
      supported: true,
      available: true,
    });
    vi.spyOn(localAiClient, "runOllamaBenchmark").mockResolvedValue([
      {
        case_id: "grounded_answer",
        provider: "ollama",
        model: "ghost:1b",
        success: false,
        timed_out: false,
        first_token_ms: null,
        total_ms: 10,
        structured_output_valid: false,
        output: "",
        error: "model_not_installed",
      },
    ]);
    const s = await buildLocalAiSnapshot({ mode: "http", probeWithBenchmark: true });
    expect(s.runtimeStatus).toBe("selected_missing");
  });

  it("probe timeout marks not_running", async () => {
    vi.spyOn(assistantStatus, "fetchAssistantRuntimeStatus").mockResolvedValue({
      configured: true,
      provider: "ollama",
      available: true,
    });
    vi.spyOn(localAiClient, "fetchSystemReadiness").mockResolvedValue({
      local_model: { status: "configured", detail: "m1" },
    });
    vi.spyOn(localAiClient, "fetchInstalledLocalModels").mockResolvedValue({
      models: ["m1"],
      supported: true,
      available: true,
    });
    vi.spyOn(localAiClient, "runOllamaBenchmark").mockResolvedValue([
      {
        case_id: "grounded_answer",
        provider: "ollama",
        model: "m1",
        success: false,
        timed_out: true,
        first_token_ms: null,
        total_ms: 120000,
        structured_output_valid: false,
        output: "",
        error: "timeout",
      },
    ]);
    const s = await buildLocalAiSnapshot({ mode: "http", probeWithBenchmark: true });
    expect(s.runtimeStatus).toBe("not_running");
  });

  it("light probe marks ready without benchmark when assistant is reachable", async () => {
    vi.spyOn(assistantStatus, "fetchAssistantRuntimeStatus").mockResolvedValue({
      configured: true,
      provider: "ollama",
      available: true,
    });
    vi.spyOn(localAiClient, "fetchSystemReadiness").mockResolvedValue({
      local_model: { status: "configured", detail: "m1" },
    });
    vi.spyOn(localAiClient, "fetchInstalledLocalModels").mockResolvedValue({
      models: ["m1"],
      supported: true,
      available: true,
    });
    const bench = vi.spyOn(localAiClient, "runOllamaBenchmark");
    const s = await buildLocalAiSnapshot({ mode: "http", probeRuntime: true });
    expect(s.runtimeStatus).toBe("ready");
    expect(bench).not.toHaveBeenCalled();
  });

  it("http runtime stopped with probe", async () => {
    vi.spyOn(assistantStatus, "fetchAssistantRuntimeStatus").mockResolvedValue({
      configured: true,
      provider: "ollama",
      available: false,
    });
    vi.spyOn(localAiClient, "fetchSystemReadiness").mockResolvedValue({
      local_model: { status: "configured", detail: "m1" },
    });
    vi.spyOn(localAiClient, "fetchInstalledLocalModels").mockResolvedValue({
      models: ["m1"],
      supported: true,
      available: false,
    });
    const s = await buildLocalAiSnapshot({ mode: "http" });
    expect(s.runtimeStatus).toBe("not_running");
  });
});
