import type { AssistantStatus } from "@/lib/domain/assistant";

const INTERNAL_STATUS_PATTERN =
  /\b(canvas_truth|system policy|provider contract|application rules|developer)\b/i;

/** User-facing activity line while the model prepares a response. */
export function assistantActivityLabel(input: string | AssistantStatus): string {
  const raw = typeof input === "string" ? input : input;
  if (typeof raw !== "string") {
    switch (raw) {
      case "thinking":
        return "Preparing explanation…";
      case "streaming":
        return "Writing response…";
      default:
        return "Working on your question…";
    }
  }
  const trimmed = raw.trim();
  if (!trimmed || INTERNAL_STATUS_PATTERN.test(trimmed)) {
    return "Preparing explanation…";
  }
  const lower = trimmed.toLowerCase();
  if (lower.includes("assignment")) return "Finding assignment…";
  if (lower.includes("material") || lower.includes("document") || lower.includes("lecture")) {
    return "Checking course materials…";
  }
  if (lower.includes("read") || lower.includes("index")) return "Reading course content…";
  if (lower.includes("retrieve") || lower.includes("search")) return "Checking course materials…";
  if (lower.includes("think")) return "Preparing explanation…";
  return trimmed.endsWith("…") ? trimmed : `${trimmed}…`;
}
