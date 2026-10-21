import type { LocalAiRuntimeStatus } from "@/lib/domain/local-ai";

const INTERNAL =
  /(traceback|exception|127\.0\.0\.1|localhost|11434|ollama:\/\/|\.env|token|sqlalchemy|httpx)/i;

export function sanitizeLocalAiDetail(detail: string | null | undefined): string | null {
  if (!detail?.trim()) return null;
  if (INTERNAL.test(detail)) return null;
  return detail.trim();
}

export function runtimeStatusHeadline(status: LocalAiRuntimeStatus): string {
  switch (status) {
    case "ready":
      return "Local AI ready";
    case "not_installed":
      return "Local AI needs setup";
    case "not_running":
      return "Local AI is not running";
    case "needs_model":
      return "Local AI needs a model";
    case "selected_missing":
      return "Selected model is not available";
    case "demo":
      return "Demo assistant (sample data)";
    case "error":
      return "Local AI problem";
    default:
      return "Checking Local AI…";
  }
}

export function runtimeStatusDetail(status: LocalAiRuntimeStatus): string {
  switch (status) {
    case "ready":
      return "Your answers can run privately on this computer.";
    case "not_installed":
      return "Install the Local AI runtime once so coursework can stay on your device.";
    case "not_running":
      return "Start the Local AI runtime, then check again.";
    case "needs_model":
      return "Install at least one AI model for the Local AI runtime.";
    case "selected_missing":
      return "Choose another installed model or install the one Hey Canvas expects.";
    case "demo":
      return "Synthetic demo mode — not your real courses.";
    case "error":
      return "Something went wrong. Try again or open Local AI settings.";
    default:
      return "Hang on while we check Local AI on this computer.";
  }
}

export function benchmarkErrorLabel(code: string | null | undefined): string {
  if (!code) return "This model could not complete the test.";
  const lower = code.toLowerCase();
  if (lower.includes("model_not_installed")) return "This model is not installed.";
  if (lower.includes("timeout")) return "The test timed out.";
  if (lower === "httperror" || lower.includes("unavailable")) {
    return "Local AI runtime is not reachable.";
  }
  return "This model could not complete the test.";
}

export const OLLAMA_INSTALL_URL = "https://ollama.com/download";

export const LOCAL_AI_SETUP_INTRO =
  "Hey Canvas uses Local AI so your coursework can stay on your computer.";

export const BENCHMARK_PRIVACY_NOTE =
  "Comparison uses short practice prompts only. Your Canvas courses, assignments, and materials are never sent into these tests.";
