import { proxyAssistantStream } from "@/lib/api/http/assistant-stream-proxy";
import { resolveBackendOrigin } from "@/lib/api/http/backend-origin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Long local Ollama runs; must exceed backend ASSISTANT_REQUEST_TIMEOUT_SECONDS. */
export const maxDuration = 300;

/**
 * Same-origin streaming proxy for POST /api/assistant/stream.
 * Route handlers take precedence over next.config rewrites so SSE is not buffered or cut off.
 */
export async function POST(request: Request): Promise<Response> {
  return proxyAssistantStream(request, resolveBackendOrigin());
}
