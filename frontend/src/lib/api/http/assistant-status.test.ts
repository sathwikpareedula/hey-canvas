/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { describeAssistantRuntimeStatus } from "@/lib/api/http/assistant-status";

describe("describeAssistantRuntimeStatus", () => {
  it("describes synthetic provider in explicit demo mode", () => {
    const prev = process.env.NEXT_PUBLIC_ACADEMIC_API_MODE;
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "mock";
    expect(
      describeAssistantRuntimeStatus({
        configured: true,
        provider: "synthetic",
        available: true,
      }),
    ).toMatch(/synthetic/i);
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = prev;
  });

  it("does not label personal http synthetic as demo", () => {
    const prev = process.env.NEXT_PUBLIC_ACADEMIC_API_MODE;
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "http";
    expect(
      describeAssistantRuntimeStatus({
        configured: true,
        provider: "synthetic",
        available: true,
      }),
    ).toMatch(/not configured/i);
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = prev;
  });

  it("describes unavailable ollama config", () => {
    expect(
      describeAssistantRuntimeStatus({
        configured: false,
        provider: "ollama",
        available: false,
      }),
    ).toMatch(/not set up/i);
  });
});
