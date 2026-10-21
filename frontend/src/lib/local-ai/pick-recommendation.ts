import type { BenchmarkResult } from "@/lib/domain/local-ai";

/**
 * Deterministic pick: among successful runs, prefer lowest total_ms with structured JSON case valid.
 * No fake quality scores — measurement-based only.
 */
export function pickRecommendedModelFromBenchmarks(
  results: BenchmarkResult[],
): string | null {
  const byModel = new Map<string, BenchmarkResult[]>();
  for (const row of results) {
    if (!byModel.has(row.model)) byModel.set(row.model, []);
    byModel.get(row.model)!.push(row);
  }

  let best: { model: string; score: number } | null = null;
  for (const [model, rows] of byModel) {
    const successes = rows.filter((r) => r.success && !r.timed_out);
    if (!successes.length) continue;
    const structuredOk = successes.some((r) => r.case_id === "structured_json" && r.structured_output_valid);
    const avgTotal =
      successes.reduce((sum, r) => sum + r.total_ms, 0) / successes.length;
    const score = avgTotal + (structuredOk ? 0 : 5000);
    if (!best || score < best.score) {
      best = { model, score };
    }
  }
  return best?.model ?? null;
}
