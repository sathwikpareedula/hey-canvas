"use client";

import { useCallback, useEffect, useState } from "react";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import {
  fetchInstalledLocalModels,
  runOllamaBenchmark,
  selectLocalAiModel,
} from "@/lib/api/http/local-ai-client";
import type { BenchmarkResult, LocalAiSnapshot } from "@/lib/domain/local-ai";
import { DEFAULT_BENCHMARK_CASES } from "@/lib/domain/local-ai";
import { buildLocalAiSnapshot } from "@/lib/local-ai/build-snapshot";
import { pickRecommendedModelFromBenchmarks } from "@/lib/local-ai/pick-recommendation";
import { benchmarkErrorLabel } from "@/lib/local-ai/student-messages";

export function useLocalAi(probeRuntime = false) {
  const { mode } = useBackendStatus();
  const { settings, updateAi, refresh: refreshProduct } = useProductSettings();
  const [snapshot, setSnapshot] = useState<LocalAiSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testState, setTestState] = useState<"idle" | "running" | "passed" | "failed">("idle");
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [benchmarkBusy, setBenchmarkBusy] = useState(false);
  const [benchmarkResults, setBenchmarkResults] = useState<BenchmarkResult[] | null>(null);
  const [recommendedModel, setRecommendedModel] = useState<string | null>(null);
  const [selectionBusy, setSelectionBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await buildLocalAiSnapshot({
        mode,
        probeRuntime: mode === "http" && probeRuntime,
        // Readiness must stay a lightweight reachability/model-discovery check.
        // A cold local model can legitimately exceed the benchmark timeout;
        // inference is tested only when the student presses "Test Local AI".
        probeWithBenchmark: false,
      });
      const discovery = await fetchInstalledLocalModels();
      next.discoverySupported = discovery.supported;
      if (discovery.models.length) {
        next.installedModels = discovery.models;
        next.installedModelsSource = "backend";
      }
      setSnapshot(next);
    } catch {
      setError("Could not refresh Local AI status. Try again.");
    } finally {
      setLoading(false);
    }
  }, [mode, probeRuntime]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void reload();
    }, 0);
    return () => window.clearTimeout(id);
  }, [reload]);

  const selectModel = useCallback(
    async (model: string) => {
      setSelectionBusy(true);
      setError(null);
      try {
        const ok = await selectLocalAiModel(model);
        if (!ok) {
          setError(
            "Saving your model choice is not available yet on this Hey Canvas service. Ask your maintainer to enable model selection.",
          );
          return false;
        }
        await reload();
        refreshProduct();
        return true;
      } catch {
        setError("Could not save that model. Try another installed model.");
        return false;
      } finally {
        setSelectionBusy(false);
      }
    },
    [reload, refreshProduct],
  );

  const testSelectedModel = useCallback(async () => {
    const model = snapshot?.selectedModel ?? snapshot?.installedModels[0];
    if (!model) {
      setTestState("failed");
      setTestMessage("Install a model before testing.");
      return;
    }
    setTestState("running");
    setTestMessage(null);
    try {
      const rows = await runOllamaBenchmark([model], [DEFAULT_BENCHMARK_CASES[0]]);
      const row = rows[0];
      if (row?.success) {
        setTestState("passed");
        setTestMessage("Local AI responded to a short practice prompt.");
      } else {
        setTestState("failed");
        setTestMessage(benchmarkErrorLabel(row?.error));
      }
    } catch {
      setTestState("failed");
      setTestMessage("Local AI test could not run. Check that the runtime is started.");
    }
  }, [snapshot]);

  const runBenchmark = useCallback(async (models: string[]) => {
    if (!models.length) return;
    setBenchmarkBusy(true);
    setBenchmarkResults(null);
    setRecommendedModel(null);
    setError(null);
    try {
      const rows = await runOllamaBenchmark(models, DEFAULT_BENCHMARK_CASES);
      setBenchmarkResults(rows);
      setRecommendedModel(pickRecommendedModelFromBenchmarks(rows));
    } catch {
      setError("Model comparison could not run. Check Local AI and try again.");
    } finally {
      setBenchmarkBusy(false);
    }
  }, []);

  const setProcessingMode = useCallback(
    (processing: "local" | "cloud") => {
      void updateAi({
        aiProcessingMode: processing,
        privacyCloudOptInAcknowledged: processing === "cloud" ? true : undefined,
      });
    },
    [updateAi],
  );

  return {
    snapshot,
    loading,
    error,
    reload,
    testState,
    testMessage,
    testSelectedModel,
    benchmarkBusy,
    benchmarkResults,
    recommendedModel,
    runBenchmark,
    selectModel,
    selectionBusy,
    aiProcessingMode: settings?.aiProcessingMode ?? "local",
    setProcessingMode,
    localModelTier: settings?.localModelTier ?? "recommended",
    updateTier: (tier: "lightweight" | "recommended" | "higher_quality") =>
      void updateAi({ localModelTier: tier }),
  };
}
