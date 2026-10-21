import type { AcademicApi } from "@/lib/api/academic-api";
import { getApiMode } from "@/lib/api";
import type { AssistantTransport } from "@/lib/assistant/transports/mock-transport";
import { createHttpAssistantTransport } from "@/lib/assistant/transports/http-transport";
import { createMockAssistantTransport } from "@/lib/assistant/transports/mock-transport";

import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";

export function createAssistantTransport(api: AcademicApi): AssistantTransport {
  return getApiMode() === "http"
    ? createHttpAssistantTransport(resolveApiBaseUrl())
    : createMockAssistantTransport(api);
}
