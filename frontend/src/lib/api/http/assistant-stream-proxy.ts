import { LOCAL_API_CLIENT_HEADER, LOCAL_API_CLIENT_VALUE } from "@/lib/api/http/local-api-headers";

/** Mirrors backend LOCAL_API_MAX_BODY_BYTES (default) so oversized bodies never reach FastAPI. */
export const MAX_STREAM_PROXY_BODY_BYTES = 512_000;

function jsonError(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Forward POST /api/assistant/stream to the local backend.
 *
 * The browser must present the local client header (a non-simple header, so a cross-site page
 * cannot send it without a failed CORS preflight); the proxy then forwards it, because the
 * backend guard requires it on every state-changing API request.
 */
export async function proxyAssistantStream(
  request: Request,
  backendOrigin: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  if (request.headers.get(LOCAL_API_CLIENT_HEADER) !== LOCAL_API_CLIENT_VALUE) {
    return jsonError(403, "This request was blocked for your privacy.");
  }
  const declared = request.headers.get("content-length");
  if (declared !== null && Number(declared) > MAX_STREAM_PROXY_BODY_BYTES) {
    return jsonError(413, "Request body is too large.");
  }
  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_STREAM_PROXY_BODY_BYTES) {
    return jsonError(413, "Request body is too large.");
  }

  let upstream: Response;
  try {
    upstream = await fetchImpl(`${backendOrigin}/api/assistant/stream`, {
      method: "POST",
      headers: {
        "Content-Type": request.headers.get("content-type") ?? "application/json",
        Accept: "text/event-stream",
        [LOCAL_API_CLIENT_HEADER]: LOCAL_API_CLIENT_VALUE,
      },
      body,
      cache: "no-store",
      // Propagate browser cancellation so the backend can stop the local model run.
      signal: request.signal,
    });
  } catch {
    return jsonError(502, "Hey Canvas could not reach its local service.");
  }

  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  headers.set("Cache-Control", "no-cache, no-transform");
  headers.set("Connection", "keep-alive");
  headers.set("X-Accel-Buffering", "no");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}
