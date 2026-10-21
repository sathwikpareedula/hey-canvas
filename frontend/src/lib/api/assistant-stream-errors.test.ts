import { describe, expect, it } from "vitest";
import { presentAssistantStreamError } from "@/lib/api/assistant-stream-errors";

describe("presentAssistantStreamError", () => {
  it("replaces raw browser network error text", () => {
    const out = presentAssistantStreamError("network error");
    expect(out.toLowerCase()).toContain("connection");
    expect(out).not.toBe("network error");
  });
});
