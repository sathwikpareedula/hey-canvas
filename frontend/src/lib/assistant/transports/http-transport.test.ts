/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { createHttpAssistantTransport } from "@/lib/assistant/transports/http-transport";

describe("http assistant transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("streams SSE events from the real assistant endpoint shape", async () => {
    const body =
      'event: started\ndata: {"type":"started","session_id":"s1"}\n\n' +
      'event: text_delta\ndata: {"type":"text_delta","text":"Hi"}\n\n' +
      'event: completed\ndata: {"type":"completed","response":{"status":"ok","blocks":[{"type":"text","text":"Done"}]}}\n\n';

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        body: {
          getReader: () => {
            let sent = false;
            return {
              read: async () => {
                if (!sent) {
                  sent = true;
                  return { done: false, value: new TextEncoder().encode(body) };
                }
                return { done: true, value: undefined };
              },
              cancel: async () => undefined,
            };
          },
        },
      })),
    );

    const transport = createHttpAssistantTransport("http://127.0.0.1:8000");
    const types: string[] = [];
    for await (const event of transport.send({ query: "hello" })) {
      types.push(event.type);
    }
    expect(types).toContain("start");
    expect(types).toContain("text_delta");
    expect(types).toContain("complete");
  });

  it("yields cancelled on abort before fetch completes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise(() => {
            /* never resolves */
          }),
      ),
    );
    const transport = createHttpAssistantTransport("http://127.0.0.1:8000");
    const abort = new AbortController();
    abort.abort();
    const events = [];
    for await (const event of transport.send({ query: "x" }, { signal: abort.signal })) {
      events.push(event);
    }
    expect(events[0]?.type).toBe("cancelled");
  });

  it("does not interpret a truncated stream as an academically valid answer", async () => {
    const body = 'event: started\ndata: {"type":"started"}\n\n' +
      'event: text_delta\ndata: {"type":"text_delta","text":"Unverified"}\n\n';
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      status: 200,
      body: {
        getReader: () => {
          let first = true;
          return {
            read: async () => {
              if (!first) return { done: true, value: undefined };
              first = false;
              return { done: false, value: new TextEncoder().encode(body) };
            },
            cancel: async () => undefined,
          };
        },
      },
    })));
    const types: string[] = [];
    for await (const event of createHttpAssistantTransport("http://127.0.0.1:8000").send({
      query: "Explain Quiz 3",
    })) {
      types.push(event.type);
    }
    expect(types).toEqual(["start", "text_delta", "transport_error"]);
  });

  it("emits exactly one final event when the backend duplicates completed", async () => {
    const end = 'event: completed\ndata: {"type":"completed","response":{"status":"ok","blocks":[{"type":"text","text":"Grounded"}]}}\n\n';
    const body = 'event: started\ndata: {"type":"started"}\n\n' + end + end;
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      status: 200,
      body: {
        getReader: () => {
          let first = true;
          return {
            read: async () => {
              if (!first) return { done: true, value: undefined };
              first = false;
              return { done: false, value: new TextEncoder().encode(body) };
            },
            cancel: async () => undefined,
          };
        },
      },
    })));
    const types: string[] = [];
    for await (const event of createHttpAssistantTransport("http://127.0.0.1:8000").send({
      query: "Explain Quiz 3",
    })) {
      types.push(event.type);
    }
    expect(types).toEqual(["start", "complete"]);
  });

});
