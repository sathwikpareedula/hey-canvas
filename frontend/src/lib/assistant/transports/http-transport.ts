import { AcademicApiError } from "@/lib/api/errors";
import { messageFromHttpErrorBody } from "@/lib/api/http/parse-api-error";
import {
  mapBackendSsePayloadToTransportEvents,
  mapTransportRequestToBackendBody,
} from "@/lib/api/http/assistant-adapters";
import { AssistantSseDecoder } from "@/lib/api/http/assistant-stream-parser";
import { localApiClientHeaders } from "@/lib/api/http/local-api-headers";
import type { AssistantTransportRequest } from "@/lib/assistant/request-mapper";
import type { AssistantTransport } from "@/lib/assistant/transports/mock-transport";
import type { AssistantTransportEvent } from "@/lib/assistant/stream-events";

export function createHttpAssistantTransport(baseUrl: string): AssistantTransport {
  const root = baseUrl.replace(/\/$/, "");

  return {
    async *send(
      request: AssistantTransportRequest,
      options?: { signal?: AbortSignal },
    ): AsyncIterable<AssistantTransportEvent> {
      if (options?.signal?.aborted) {
        yield { type: "cancelled" };
        return;
      }

      try {
        const res = await fetch(`${root}/api/assistant/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            ...localApiClientHeaders(),
          },
          body: JSON.stringify(mapTransportRequestToBackendBody(request)),
          signal: options?.signal,
        });

        if (!res.ok) {
          const detail = await res.text().catch(() => "");
          yield {
            type: "transport_error",
            error: new AcademicApiError(
              messageFromHttpErrorBody(res.status, detail),
              res.status,
              res.status === 503 ? "network" : "http",
            ),
          };
          return;
        }

        if (!res.body) {
          yield {
            type: "transport_error",
            error: new AcademicApiError("Assistant stream had no body", undefined, "malformed"),
          };
          return;
        }

        const decoder = new AssistantSseDecoder();
        const reader = res.body.getReader();
        let sawTerminal = false;

        while (true) {
          if (options?.signal?.aborted) {
            yield { type: "cancelled" };
            await reader.cancel().catch(() => undefined);
            return;
          }
          const { done, value } = await reader.read();
          if (done) break;
          const frames = decoder.push(value);
          for (const frame of frames) {
            for (const mapped of mapBackendSsePayloadToTransportEvents(frame.event, frame.data)) {
              if (sawTerminal) break;
              if (mapped.type === "complete" || mapped.type === "error") sawTerminal = true;
              yield mapped;
            }
            if (sawTerminal) break;
          }
          if (sawTerminal) {
            await reader.cancel().catch(() => undefined);
            return;
          }
        }

        for (const frame of decoder.flush()) {
          for (const mapped of mapBackendSsePayloadToTransportEvents(frame.event, frame.data)) {
            if (sawTerminal) break;
            if (mapped.type === "complete" || mapped.type === "error") sawTerminal = true;
            yield mapped;
          }
          if (sawTerminal) break;
        }
        if (!sawTerminal && !options?.signal?.aborted) {
          yield {
            type: "transport_error",
            error: new AcademicApiError(
              "Assistant stream ended without a validated final response.",
              undefined,
              "malformed",
            ),
          };
        }
      } catch (err) {
        if (options?.signal?.aborted) {
          yield { type: "cancelled" };
          return;
        }
        yield { type: "transport_error", error: err };
      }
    },
  };
}
