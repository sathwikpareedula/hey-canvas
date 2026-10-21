/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it } from "vitest";
import { getApiMode, isExplicitDemoMode } from "@/lib/api/app-mode";

const keys = ["NEXT_PUBLIC_ACADEMIC_API_MODE", "NEXT_PUBLIC_HEY_CANVAS_DEMO"] as const;

describe("app-mode", () => {
  const prev: Record<string, string | undefined> = {};
  afterEach(() => {
    for (const k of keys) {
      if (prev[k] === undefined) delete process.env[k];
      else process.env[k] = prev[k];
    }
  });

  it("defaults to http personal mode", () => {
    delete process.env.NEXT_PUBLIC_ACADEMIC_API_MODE;
    delete process.env.NEXT_PUBLIC_HEY_CANVAS_DEMO;
    expect(getApiMode()).toBe("http");
    expect(isExplicitDemoMode()).toBe(false);
  });

  it("mock env enables explicit demo", () => {
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "mock";
    expect(getApiMode()).toBe("mock");
    expect(isExplicitDemoMode()).toBe(true);
  });
});
