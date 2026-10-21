/** Student-facing Local AI state (provider-agnostic product model). */

export type LocalAiRuntimeStatus =
  | "ready"
  | "not_installed"
  | "not_running"
  | "needs_model"
  | "selected_missing"
  | "error"
  | "unknown"
  | "demo";

export type LocalAiModelTestState = "idle" | "running" | "passed" | "failed";

export interface LocalAiSnapshot {
  runtimeStatus: LocalAiRuntimeStatus;
  statusHeadline: string;
  statusDetail: string | null;
  selectedModel: string | null;
  installedModels: string[];
  installedModelsSource: "backend" | "inferred" | "none";
  provider: string | null;
  assistantConfigured: boolean;
  discoverySupported: boolean;
  selectionSupported: boolean;
  benchmarkSupported: boolean;
  updatedAt: string;
}

export interface BenchmarkCase {
  case_id: string;
  prompt: string;
}

export interface BenchmarkResult {
  case_id: string;
  provider: string;
  model: string;
  success: boolean;
  timed_out: boolean;
  first_token_ms: number | null;
  total_ms: number;
  structured_output_valid: boolean;
  output: string;
  error?: string | null;
}

export interface BenchmarkComparisonRow {
  model: string;
  results: BenchmarkResult[];
  allSucceeded: boolean;
  anyTimedOut: boolean;
}

/** Synthetic tasks only — never course or Canvas content. */
export const DEFAULT_BENCHMARK_CASES: BenchmarkCase[] = [
  {
    case_id: "short_reply",
    prompt: "Reply with exactly one word: OK",
  },
  {
    case_id: "structured_json",
    prompt: 'Return only JSON: {"ok":true}',
  },
  {
    case_id: "grounded_explanation",
    prompt:
      "In 2 sentences, explain what a course syllabus is to a new college student. Do not invent specific dates or grades.",
  },
  {
    case_id: "assignment_instruction",
    prompt:
      "A homework says: submit a PDF report and cite two sources. In one sentence, list what the student must do.",
  },
  {
    case_id: "course_followup",
    prompt:
      "Prior topic: office hours. Student asks: when should I go? Reply in one short sentence about preparing questions.",
  },
  {
    case_id: "structured_extraction",
    prompt:
      'Extract fields from this synthetic line only: "Course=CSE3310; Due=Friday; Points=10". Return JSON with keys course, due, points.',
  },
  {
    case_id: "small_synthesis",
    prompt:
      "Combine these two synthetic facts: (1) Quiz on chapter 3 Friday. (2) Lab report due next Monday. One sentence study plan.",
  },
];
