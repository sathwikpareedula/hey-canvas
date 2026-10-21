/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { createHttpAssistantTransport } from "@/lib/assistant/transports/http-transport";

const runProxy =
  process.env.RUN_ASSISTANT_PROXY_INTEGRATION === "1" &&
  process.env.ASSISTANT_PROXY_BASE_URL;

describe.runIf(Boolean(runProxy))("assistant stream via Next proxy route", () => {
  it("reaches a terminal completed event", async () => {
    const base = process.env.ASSISTANT_PROXY_BASE_URL!;
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "http";
    const transport = createHttpAssistantTransport(base);
    const types: string[] = [];
    for await (const event of transport.send({
      query: "Reply with exactly: proxy-ok",
      courseId: process.env.ASSISTANT_PROXY_COURSE_ID ?? "278791",
    })) {
      types.push(event.type);
      if (event.type === "complete" || event.type === "error") break;
    }
    expect(types).toContain("start");
    expect(types[types.length - 1]).toBe("complete");
  }, 320_000);
});
