import type { AssistantStreamEvent } from "@/lib/domain/assistant";
import type { AssistantTransportEvent } from "@/lib/assistant/stream-events";
import { assistantActivityLabel } from "@/lib/product/assistant-activity-label";
import { sanitizeAssistantBlock } from "@/lib/assistant/normalize-block";

/** Maps existing AcademicApi stream events to transport events until HTTP contract lands. */
export function mapLegacyStreamEvent(event: AssistantStreamEvent): AssistantTransportEvent[] {
  switch (event.type) {
    case "status":
      return [{ type: "activity", message: assistantActivityLabel(event.status) }];
    case "text_delta":
      return [{ type: "text_delta", delta: event.delta }];
    case "block":
      return [{ type: "block", block: sanitizeAssistantBlock(event.block) }];
    case "done":
      return [{ type: "complete", message: event.message }];
    case "error":
      return [{ type: "error", message: event.message, retryable: true }];
    default:
      return [];
  }
}
