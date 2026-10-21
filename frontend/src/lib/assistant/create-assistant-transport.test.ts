/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockAcademicApi } from "@/lib/api/mock-academic-api";
import { createAssistantTransport } from "@/lib/assistant/create-assistant-transport";

describe("createAssistantTransport", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses mock transport in mock API mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_ACADEMIC_API_MODE", "mock");
    const transport = createAssistantTransport(new MockAcademicApi());
    const events = [];
    for await (const event of transport.send({ query: "What's due today?" })) {
      events.push(event);
      if (event.type === "complete") break;
    }
    expect(events.some((e) => e.type === "complete")).toBe(true);
  });

  it("uses HTTP transport in http API mode (no mock fallback)", async () => {
    vi.stubEnv("NEXT_PUBLIC_ACADEMIC_API_MODE", "http");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        text: async () => "provider unavailable",
      })),
    );
    const transport = createAssistantTransport(new MockAcademicApi());
    const events = [];
    for await (const event of transport.send({ query: "hello" })) {
      events.push(event);
    }
    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("transport_error");
  });
});
