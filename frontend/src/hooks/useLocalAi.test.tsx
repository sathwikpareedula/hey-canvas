import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLocalAi } from "@/hooks/useLocalAi";
import { buildLocalAiSnapshot } from "@/lib/local-ai/build-snapshot";

vi.mock("@/contexts/BackendStatusContext", () => ({
  useBackendStatus: () => ({ mode: "http" }),
}));

vi.mock("@/contexts/ProductSettingsContext", () => ({
  useProductSettings: () => ({
    settings: { aiProcessingMode: "local", localModelTier: "recommended" },
    updateAi: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/local-ai/build-snapshot", () => ({
  buildLocalAiSnapshot: vi.fn(),
}));

vi.mock("@/lib/api/http/local-ai-client", () => ({
  fetchInstalledLocalModels: vi.fn(async () => ({
    models: ["llama3.2:3b"],
    supported: true,
    available: true,
  })),
  runOllamaBenchmark: vi.fn(),
  selectLocalAiModel: vi.fn(),
}));

describe("useLocalAi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(buildLocalAiSnapshot).mockResolvedValue({
      runtimeStatus: "ready",
      statusHeadline: "Local AI ready",
      statusDetail: "Available",
      selectedModel: "llama3.2:3b",
      installedModels: ["llama3.2:3b"],
      installedModelsSource: "backend",
      provider: "ollama",
      assistantConfigured: true,
      discoverySupported: true,
      selectionSupported: true,
      benchmarkSupported: true,
      updatedAt: "2026-10-17T00:00:00Z",
    });
  });

  it("uses lightweight discovery for automatic status refresh", async () => {
    const { result } = renderHook(() => useLocalAi(true));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(buildLocalAiSnapshot).toHaveBeenCalledWith({
      mode: "http",
      probeRuntime: true,
      probeWithBenchmark: false,
    });
    expect(result.current.snapshot?.runtimeStatus).toBe("ready");
  });
});
