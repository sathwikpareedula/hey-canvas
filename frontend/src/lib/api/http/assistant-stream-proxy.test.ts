/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from "vitest";
import {
  MAX_STREAM_PROXY_BODY_BYTES,
  proxyAssistantStream,
} from "@/lib/api/http/assistant-stream-proxy";
import { LOCAL_API_CLIENT_HEADER, LOCAL_API_CLIENT_VALUE } from "@/lib/api/http/local-api-headers";

function makeRequest(init: { headers?: Record<string, string>; body?: string; signal?: AbortSignal }) {
  return new Request("http://localhost:3001/api/assistant/stream", {
    method: "POST",
    headers: init.headers,
    body: init.body ?? "{}",
    signal: init.signal,
  });
}

const trusted = { [LOCAL_API_CLIENT_HEADER]: LOCAL_API_CLIENT_VALUE, "content-type": "application/json" };

describe("assistant stream proxy", () => {
  it("forwards the local client header so the backend guard accepts the request", async () => {
    const fetchImpl = vi.fn(async () => new Response("event: completed\n\n"));
    const response = await proxyAssistantStream(
      makeRequest({ headers: trusted }),
      "http://127.0.0.1:8000",
      fetchImpl as unknown as typeof fetch,
    );
    expect(response.status).toBe(200);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/assistant/stream");
    expect((init.headers as Record<string, string>)[LOCAL_API_CLIENT_HEADER]).toBe(
      LOCAL_API_CLIENT_VALUE,
    );
  });

  it("rejects requests without the local client header and never contacts the backend", async () => {
    const fetchImpl = vi.fn();
    const response = await proxyAssistantStream(
      makeRequest({ headers: { "content-type": "text/plain" } }),
      "http://127.0.0.1:8000",
      fetchImpl as unknown as typeof fetch,
    );
    expect(response.status).toBe(403);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("rejects oversized bodies before contacting the backend", async () => {
    const fetchImpl = vi.fn();
    const response = await proxyAssistantStream(
      makeRequest({ headers: trusted, body: "x".repeat(MAX_STREAM_PROXY_BODY_BYTES + 1) }),
      "http://127.0.0.1:8000",
      fetchImpl as unknown as typeof fetch,
    );
    expect(response.status).toBe(413);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("propagates browser cancellation to the backend request", async () => {
    const fetchImpl = vi.fn(async () => new Response(""));
    const controller = new AbortController();
    await proxyAssistantStream(
      makeRequest({ headers: trusted, signal: controller.signal }),
      "http://127.0.0.1:8000",
      fetchImpl as unknown as typeof fetch,
    );
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.signal).toBeDefined();
    controller.abort();
    expect(init.signal?.aborted).toBe(true);
  });

  it("returns a sanitized 502 when the backend is unreachable", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("connect ECONNREFUSED 127.0.0.1:8000 C:\\private\\academic.db");
    });
    const response = await proxyAssistantStream(
      makeRequest({ headers: trusted }),
      "http://127.0.0.1:8000",
      fetchImpl as unknown as typeof fetch,
    );
    expect(response.status).toBe(502);
    const text = await response.text();
    expect(text).not.toContain("academic.db");
    expect(text).not.toContain("ECONNREFUSED");
  });
});
