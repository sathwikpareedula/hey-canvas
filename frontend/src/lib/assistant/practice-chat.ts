import type { AssistantRequest } from "@/lib/domain/assistant";

/** Build assistant fields for in-chat practice follow-ups (explicit actions only). */
export function practiceHintRequest(sessionId: string): Pick<
  AssistantRequest,
  "prompt" | "practiceSessionId" | "operation"
> {
  return {
    prompt: "hint",
    practiceSessionId: sessionId,
    operation: "answer",
  };
}

export function practiceAnswerRequest(
  sessionId: string,
  answer: string,
): Pick<AssistantRequest, "prompt" | "practiceSessionId" | "answer" | "operation"> {
  return {
    prompt: "check my answer",
    practiceSessionId: sessionId,
    answer: answer.trim(),
    operation: "answer",
  };
}
