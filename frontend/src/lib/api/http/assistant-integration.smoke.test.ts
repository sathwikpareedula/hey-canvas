/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { createHttpAssistantTransport } from "@/lib/assistant/transports/http-transport";
const runIntegration = process.env.RUN_ASSISTANT_INTEGRATION === "1";
const baseUrl = process.env.ASSISTANT_INTEGRATION_BASE_URL ?? "http://127.0.0.1:8000";

describe.runIf(runIntegration)("assistant integration smoke", () => {
  it("reads assistant status", async () => {
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "http";
    const status = await fetch(
      `${baseUrl}/api/assistant/status`,
    ).then((r) => r.json());
    expect(status.provider).toBe("synthetic");
    expect(status.available).toBe(true);
  });

  it("streams a synthetic response", async () => {
    const transport = createHttpAssistantTransport(baseUrl);
    const types: string[] = [];
    for await (const event of transport.send({ query: "What do I have due today?" })) {
      types.push(event.type);
      if (event.type === "complete") break;
    }
    expect(types).toContain("start");
    expect(types).toContain("complete");
  });
});
