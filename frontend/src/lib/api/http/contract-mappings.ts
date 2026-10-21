import type { StudyMode as UiStudyMode } from "@/lib/domain/study-mode";
import type { DeadlineWindow } from "@/lib/domain/types";

/** Map frontend deadline filters to Phase 7 backend query values. */
export function mapDeadlineWindowToBackend(window: DeadlineWindow): string {
  if (window === "past_due_time") return "overdue";
  return window;
}

/** Map backend study mode to Hey Canvas UI study mode. */
export function mapBackendStudyModeToUi(
  backend: string | null | undefined,
): UiStudyMode | null {
  switch (backend) {
    case "exam_prep":
      return "exam";
    case "review":
      return "review";
    case "practice":
      return "practice";
    case "balanced":
      return "learn";
    default:
      return null;
  }
}

export function mapUiStudyModeToBackend(mode: UiStudyMode): string {
  switch (mode) {
    case "exam":
      return "exam_prep";
    case "learn":
      return "balanced";
    default:
      return mode;
  }
}

/** Assistant API uses `query`; UI uses `prompt`. */
export function mapPromptToAssistantQuery(prompt: string): string {
  return prompt.trim();
}

/** Map backend session id to frontend conversation id. */
export function mapSessionIdToConversationId(sessionId: string | null | undefined): string | undefined {
  if (!sessionId || typeof sessionId !== "string") return undefined;
  return sessionId;
}
