import type { ChatMessage } from "@/lib/domain/types";

export const ASSISTANT_EMPTY_RECOVERY_MESSAGE =
  "The assistant did not return an answer. Check that local AI is running in Settings, then try again or rephrase your question.";

export function messageHasVisibleAssistantContent(message: ChatMessage): boolean {
  const blocks = message.blocks ?? [];
  if (blocks.length === 0) return Boolean(message.text?.trim());
  return blocks.some((b) => {
    if (b.type === "text") return Boolean(b.content?.trim());
    if (b.type === "error" || b.type === "warning") return Boolean(b.content?.trim());
    return true;
  });
}

export function withEmptyResponseRecovery(message: ChatMessage): ChatMessage {
  if (messageHasVisibleAssistantContent(message)) return message;
  return {
    ...message,
    status: message.status === "complete" ? "error" : message.status,
    blocks: [{ type: "error", content: ASSISTANT_EMPTY_RECOVERY_MESSAGE }],
    text: undefined,
  };
}
