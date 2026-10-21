import { withEmptyResponseRecovery } from "@/lib/assistant/empty-response";
import { sanitizeAssistantBlock } from "@/lib/assistant/normalize-block";
import type {
  AssistantConversationPhase,
  AssistantTransportEvent,
} from "@/lib/assistant/stream-events";
import type { ChatMessage } from "@/lib/domain/types";

export interface AssistantSessionState {
  phase: AssistantConversationPhase;
  streamingText: string;
  pendingBlocks: ChatMessage["blocks"];
  pendingSources: number;
  activityMessage: string | null;
}

export function initialAssistantSessionState(): AssistantSessionState {
  return {
    phase: "idle",
    streamingText: "",
    pendingBlocks: [],
    pendingSources: 0,
    activityMessage: null,
  };
}

export function canSendAssistantMessage(phase: AssistantConversationPhase): boolean {
  return phase === "idle" || phase === "completed" || phase === "failed" || phase === "cancelled";
}

export interface SessionEventResult {
  state: AssistantSessionState;
  appendMessage?: ChatMessage;
  transportError?: unknown;
  retryable?: boolean;
}

export function applyTransportEvent(
  state: AssistantSessionState,
  event: AssistantTransportEvent,
): SessionEventResult {
  switch (event.type) {
    case "activity":
      return {
        state: {
          ...state,
          activityMessage: event.message,
        },
      };
    case "start":
      return {
        state: {
          ...state,
          phase: "streaming",
          streamingText: "",
          pendingBlocks: [],
          pendingSources: 0,
          activityMessage: state.activityMessage,
        },
      };
    case "text_delta":
      return {
        state: {
          ...state,
          phase: "streaming",
          streamingText: state.streamingText + event.delta,
        },
      };
    case "block":
      return {
        state: {
          ...state,
          phase: "streaming",
          pendingBlocks: [...(state.pendingBlocks ?? []), sanitizeAssistantBlock(event.block)],
        },
      };
    case "source":
      return {
        state: {
          ...state,
          phase: "streaming",
          pendingSources: state.pendingSources + 1,
          pendingBlocks: [
            ...(state.pendingBlocks ?? []),
            {
              type: "document_answer",
              sources: [event.source],
            },
          ],
        },
      };
    case "warning":
      return {
        state: {
          ...state,
          pendingBlocks: [
            ...(state.pendingBlocks ?? []),
            { type: "warning", content: event.message },
          ],
        },
      };
    case "follow_up": {
      const last = state.pendingBlocks ?? [];
      const updated: ChatMessage["blocks"] = last.length
        ? last.map((b, i) =>
            i === last.length - 1 ? { ...b, followUps: event.suggestions } : b,
          )
        : [{ type: "text" as const, content: "", followUps: event.suggestions }];
      return {
        state: { ...state, pendingBlocks: updated },
      };
    }
    case "error":
      return {
        state: {
          ...initialAssistantSessionState(),
          phase: "failed",
        },
        appendMessage: {
          id: `err-${Date.now()}`,
          role: "assistant",
          createdAt: new Date().toISOString(),
          status: "error",
          blocks: [{ type: "error", content: event.message }],
        },
        retryable: event.retryable ?? true,
      };
    case "transport_error":
      return {
        state: {
          ...initialAssistantSessionState(),
          phase: "failed",
        },
        transportError: event.error,
        retryable: true,
        appendMessage: {
          id: `transport-${Date.now()}`,
          role: "assistant",
          createdAt: new Date().toISOString(),
          status: "error",
          blocks: [
            {
              type: "error",
              content: "The assistant could not complete this request.",
            },
          ],
        },
      };
    case "cancelled":
      return {
        state: {
          ...initialAssistantSessionState(),
          phase: "cancelled",
        },
        appendMessage: {
          id: `cancel-${Date.now()}`,
          role: "assistant",
          createdAt: new Date().toISOString(),
          status: "incomplete_data",
          blocks: [
            {
              type: "warning",
              content: "Generation stopped before the answer finished.",
            },
          ],
        },
      };
    case "complete": {
      const streamingText = state.streamingText.trim();
      let message = event.message;
      if (streamingText && !message.blocks?.some((b) => b.type === "text" && b.content?.trim())) {
        message = {
          ...message,
          blocks: [{ type: "text", content: streamingText }, ...(message.blocks ?? [])],
        };
      }
      return {
        state: {
          ...initialAssistantSessionState(),
          phase: "completed",
        },
        appendMessage: withEmptyResponseRecovery(message),
      };
    }
    default:
      return { state };
  }
}

export function beginSending(state: AssistantSessionState): AssistantSessionState {
  return {
    ...state,
    phase: "sending",
    streamingText: "",
    pendingBlocks: [],
    activityMessage: "Connecting to your local assistant…",
  };
}
