import type { AcademicApi } from "@/lib/api/academic-api";
import { mapTransportToAcademicApiRequest } from "@/lib/assistant/request-mapper";
import type { AssistantTransportRequest } from "@/lib/assistant/request-mapper";
import { mapLegacyStreamEvent } from "@/lib/assistant/transports/legacy-adapter";
import type { AssistantTransportEvent } from "@/lib/assistant/stream-events";

export interface AssistantTransport {
  send(
    request: AssistantTransportRequest,
    options?: { signal?: AbortSignal },
  ): AsyncIterable<AssistantTransportEvent>;
}

export function createMockAssistantTransport(api: AcademicApi): AssistantTransport {
  return {
    async *send(request, options) {
      const stream = api.streamAssistant?.(mapTransportToAcademicApiRequest(request));
      if (!stream) {
        yield {
          type: "transport_error",
          error: new Error("Assistant streaming is not available"),
        };
        return;
      }
      yield { type: "start", conversationId: request.conversationId };
      for await (const legacy of stream) {
        if (options?.signal?.aborted) {
          yield { type: "cancelled" };
          return;
        }
        for (const mapped of mapLegacyStreamEvent(legacy)) {
          yield mapped;
        }
      }
    },
  };
}
