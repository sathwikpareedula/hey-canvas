"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useLocalAi } from "@/hooks/useLocalAi";
import { localModelTierLabel } from "@/lib/product/ai-preferences";
import {
  BENCHMARK_PRIVACY_NOTE,
  LOCAL_AI_SETUP_INTRO,
  OLLAMA_INSTALL_URL,
} from "@/lib/local-ai/student-messages";
import { benchmarkErrorLabel } from "@/lib/local-ai/student-messages";

export function LocalAiSettingsPanel({ compact }: { compact?: boolean }) {
  const {
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
    aiProcessingMode,
    setProcessingMode,
    localModelTier,
    updateTier,
  } = useLocalAi(!compact);

  const [benchmarkSelection, setBenchmarkSelection] = useState<string[]>([]);
  const installed = snapshot?.installedModels ?? [];

  const benchmarkRows = useMemo(() => {
    if (!benchmarkResults) return [];
    const byModel = new Map<string, typeof benchmarkResults>();
    for (const row of benchmarkResults) {
      if (!byModel.has(row.model)) byModel.set(row.model, []);
      byModel.get(row.model)!.push(row);
    }
    return [...byModel.entries()];
  }, [benchmarkResults]);

  const toggleBenchmarkModel = (model: string) => {
    setBenchmarkSelection((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model],
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold">Local AI</h2>
        <p className="mt-1 text-xs text-[var(--muted)]">
          {LOCAL_AI_SETUP_INTRO} Optional cloud processing is separate in settings below.
        </p>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium text-[var(--muted)]">Processing</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="ai-mode-panel"
            checked={aiProcessingMode !== "cloud"}
            onChange={() => setProcessingMode("local")}
          />
          Local only — free and private (default)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="ai-mode-panel"
            checked={aiProcessingMode === "cloud"}
            onChange={() => setProcessingMode("cloud")}
          />
          Optional cloud / bring your own provider
        </label>
      </fieldset>

      {aiProcessingMode === "cloud" ? (
        <p className="text-xs text-[var(--muted)]">
          Cloud mode uses your configured provider on the Hey Canvas service. Local AI below is still
          available for private work when you switch back.
        </p>
      ) : null}

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-3 text-sm">
        <p className="font-medium" role="status">
          {loading ? "Checking Local AI…" : snapshot?.statusHeadline ?? "Local AI"}
        </p>
        <p className="mt-1 text-xs text-[var(--muted)]">
          {loading ? "One moment…" : snapshot?.statusDetail}
        </p>
        {snapshot?.selectedModel ? (
          <p className="mt-2 text-xs">
            Selected model: <span className="font-medium">{snapshot.selectedModel}</span>
          </p>
        ) : null}
        {error ? (
          <p className="mt-2 text-xs text-[var(--warn-text)]" role="alert">{error}</p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void reload()}
            disabled={loading}
            className="min-h-9 rounded-md border border-[var(--border)] px-3 text-xs disabled:opacity-50"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => void testSelectedModel()}
            disabled={loading || testState === "running" || aiProcessingMode === "cloud"}
            className="min-h-9 rounded-md border border-[var(--border)] px-3 text-xs disabled:opacity-50"
          >
            {testState === "running" ? "Testing…" : "Test Local AI"}
          </button>
        </div>
        {testMessage ? (
          <p
            className={`mt-2 text-xs ${testState === "passed" ? "text-emerald-700 dark:text-emerald-400" : "text-[var(--warn-text)]"}`}
            role="status"
          >
            {testMessage}
          </p>
        ) : null}
      </div>

      {snapshot?.runtimeStatus === "not_installed" ? (
        <div className="rounded-lg border border-[var(--border)] p-3 text-sm">
          <p className="font-medium">Set up Local AI</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Install the free Local AI runtime (Ollama) on this computer, then install at least one
            model. Hey Canvas will not download models for you.
          </p>
          <a
            href={OLLAMA_INSTALL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-xs text-[var(--accent)] underline"
          >
            Get the Local AI runtime (Ollama)
          </a>
        </div>
      ) : null}

      {snapshot?.runtimeStatus === "not_running" ? (
        <div className="rounded-lg border border-[var(--border)] p-3 text-sm">
          <p className="font-medium">Start Local AI</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Open the Ollama app from your Start menu, or start the Local AI runtime, then tap Refresh.
          </p>
        </div>
      ) : null}

      {snapshot?.runtimeStatus === "needs_model" || snapshot?.runtimeStatus === "selected_missing" ? (
        <div className="rounded-lg border border-[var(--border)] p-3 text-sm">
          <p className="font-medium">Install a model</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Local AI is installed, but Hey Canvas still needs an AI model. Install one using the
            Ollama app or its instructions. Downloads are large — only install what you intend to use.
          </p>
        </div>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          Installed models
        </h3>
        {!snapshot?.discoverySupported && installed.length <= 1 ? (
          <p className="text-xs text-[var(--muted)]">
            {installed.length
              ? "Showing the model configured on your Hey Canvas service. Full model list requires a backend update."
              : "No models discovered yet. Refresh after you install a model."}
          </p>
        ) : null}
        {installed.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No installed models detected.</p>
        ) : (
          <ul className="space-y-1">
            {installed.map((model) => {
              const selected = snapshot?.selectedModel === model;
              return (
                <li
                  key={model}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm"
                >
                  <span className="font-medium">{model}</span>
                  <div className="flex gap-2">
                    {selected ? (
                      <span className="text-xs text-[var(--muted)]">Selected</span>
                    ) : (
                      <button
                        type="button"
                        disabled={selectionBusy}
                        onClick={() => void selectModel(model)}
                        className="text-xs text-[var(--accent)] underline disabled:opacity-50"
                      >
                        Select
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {!compact ? (
        <details className="rounded-lg border border-[var(--border)] p-3 text-sm">
          <summary className="cursor-pointer font-medium">Advanced</summary>
          <label className="mt-3 block text-xs">
            Speed vs quality hint (when model list is unavailable)
            <select
              className="mt-1 w-full rounded-md border border-[var(--border)] px-2 py-1"
              value={localModelTier}
              onChange={(e) =>
                updateTier(e.target.value as "lightweight" | "recommended" | "higher_quality")
              }
            >
              {(["lightweight", "recommended", "higher_quality"] as const).map((tier) => (
                <option key={tier} value={tier}>{localModelTierLabel(tier)}</option>
              ))}
            </select>
          </label>
          {snapshot?.provider ? (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Runtime provider: {snapshot.provider === "ollama" ? "Ollama (local)" : snapshot.provider}
            </p>
          ) : null}
        </details>
      ) : null}

      {!compact ? (
        <section className="space-y-3 rounded-lg border border-[var(--border)] p-3">
          <h3 className="text-sm font-semibold">Compare Local AI models</h3>
          <p className="text-xs text-[var(--muted)]">{BENCHMARK_PRIVACY_NOTE}</p>
          {installed.length === 0 ? (
            <p className="text-xs text-[var(--muted)]">Install models to compare them.</p>
          ) : (
            <>
              <ul className="space-y-1">
                {installed.map((model) => (
                  <li key={model}>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={benchmarkSelection.includes(model)}
                        onChange={() => toggleBenchmarkModel(model)}
                      />
                      {model}
                    </label>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                disabled={benchmarkBusy || benchmarkSelection.length === 0}
                onClick={() => void runBenchmark(benchmarkSelection)}
                className="min-h-9 rounded-md bg-[var(--accent)] px-3 text-xs text-[var(--accent-fg)] disabled:opacity-50"
              >
                {benchmarkBusy ? "Running comparison…" : "Run comparison"}
              </button>
              {recommendedModel ? (
                <p className="text-xs text-[var(--muted)]">
                  Fastest successful run on this comparison:{" "}
                  <span className="font-medium text-[var(--foreground)]">{recommendedModel}</span>
                  {" "}(based on measured latency — not a quality score).
                </p>
              ) : null}
              {benchmarkRows.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[20rem] text-left text-xs">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="py-1 pr-2">Model</th>
                        <th className="py-1 pr-2">Task</th>
                        <th className="py-1 pr-2">Result</th>
                        <th className="py-1 pr-2">First token</th>
                        <th className="py-1 pr-2">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {benchmarkResults!.map((row) => (
                        <tr key={`${row.model}-${row.case_id}`} className="border-b border-[var(--border)]">
                          <td className="py-1 pr-2">{row.model}</td>
                          <td className="py-1 pr-2">{row.case_id}</td>
                          <td className="py-1 pr-2">
                            {row.success
                              ? "OK"
                              : row.timed_out
                                ? "Timed out"
                                : benchmarkErrorLabel(row.error)}
                          </td>
                          <td className="py-1 pr-2">
                            {row.first_token_ms != null ? `${row.first_token_ms} ms` : "—"}
                          </td>
                          <td className="py-1 pr-2">{row.total_ms} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      <p className="text-xs text-[var(--muted)]">
        <Link href="/startup" className="underline">Startup checklist</Link>
        {" · "}
        <Link href="/onboarding" className="underline">Setup wizard</Link>
      </p>
    </div>
  );
}
