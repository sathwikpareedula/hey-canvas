import type { AssistantBlock, AssistantSource, ChatMessage } from "@/lib/domain/types";

/** Provider-neutral transport events (not tied to OpenAI/Anthropic). */
export type AssistantTransportEvent =
  | { type: "start"; conversationId?: string; requestId?: string }
  | { type: "text_delta"; delta: string }
  | { type: "block"; block: AssistantBlock }
  | { type: "source"; source: AssistantSource }
  | { type: "warning"; message: string }
  | { type: "error"; message: string; retryable?: boolean }
  | { type: "follow_up"; suggestions: string[] }
  | { type: "complete"; message: ChatMessage }
  | { type: "cancelled" }
  | { type: "activity"; message: string }
  | { type: "transport_error"; error: unknown };

export type AssistantConversationPhase =
  | "idle"
  | "sending"
  | "streaming"
  | "completed"
  | "failed"
  | "cancelled";
