import { AcademicApiError } from "@/lib/api/errors";
import { fetchJson, postJson, putJson } from "@/lib/api/http/fetch-json";
import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";
import type { BenchmarkCase, BenchmarkResult } from "@/lib/domain/local-ai";
import { DEFAULT_BENCHMARK_CASES as CASES } from "@/lib/domain/local-ai";

function base(): string {
  return resolveApiBaseUrl();
}

const MODEL_LIST_PATH = "/api/benchmarks/ollama/models";

export interface SystemReadinessComponent {
  status: string;
  detail?: string | null;
}

export interface SystemReadinessResponse {
  backend?: SystemReadinessComponent;
  database?: SystemReadinessComponent;
  canvas?: SystemReadinessComponent;
  local_runtime?: SystemReadinessComponent;
  local_model?: SystemReadinessComponent;
  schema?: SystemReadinessComponent;
  last_sync?: SystemReadinessComponent;
  documents?: SystemReadinessComponent;
  privacy?: SystemReadinessComponent;
}

export async function fetchSystemReadiness(): Promise<SystemReadinessResponse | null> {
  try {
    return await fetchJson<SystemReadinessResponse>(`${base()}/api/readiness`);
  } catch (err) {
    // Unreachable backend is "no readiness data", not an unhandled rejection.
    if (
      err instanceof AcademicApiError &&
      (err.kind === "network" || err.status === 404 || err.status === 501)
    ) {
      return null;
    }
    throw err;
  }
}

export async function fetchInstalledLocalModels(): Promise<{
  models: string[];
  supported: boolean;
  available: boolean | null;
}> {
  try {
    const row = await fetchJson<Record<string, unknown>>(`${base()}${MODEL_LIST_PATH}`);
    const raw = row.models;
    if (Array.isArray(raw)) {
      const models = raw.filter((m): m is string => typeof m === "string" && m.trim().length > 0);
      return { models, supported: true, available: true };
    }
    return { models: [], supported: true, available: true };
  } catch (err) {
    if (err instanceof AcademicApiError && err.kind === "network") {
      return { models: [], supported: true, available: false };
    }
    if (err instanceof AcademicApiError && err.status === 503) {
      return { models: [], supported: true, available: false };
    }
    if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) {
      return { models: [], supported: false, available: null };
    }
    throw err;
  }
}

export async function selectLocalAiModel(model: string): Promise<boolean> {
  await putJson(`${base()}/api/local-ai/model`, { model });
  return true;
}

export async function runOllamaBenchmark(
  models: string[],
  cases: BenchmarkCase[] = CASES,
): Promise<BenchmarkResult[]> {
  const rows = await postJson<BenchmarkResult[]>(`${base()}/api/benchmarks/ollama`, {
    models,
    cases,
  });
  return Array.isArray(rows) ? rows : [];
}

export function benchmarkEndpointAvailable(): Promise<boolean> {
  return fetchInstalledLocalModels().then(async ({ supported }) => {
    if (supported) return true;
    try {
      await postJson(`${base()}/api/benchmarks/ollama`, {
        models: ["__probe__"],
        cases: [{ case_id: "probe", prompt: "OK" }],
      });
      return true;
    } catch (err) {
      if (err instanceof AcademicApiError && err.status === 404) return false;
      if (err instanceof AcademicApiError && err.status === 503) return true;
      if (err instanceof AcademicApiError && err.status === 422) return true;
      return false;
    }
  });
}
