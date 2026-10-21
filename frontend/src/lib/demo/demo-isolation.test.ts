/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { getApiMode } from "@/lib/api";
import { isSyntheticCatalog, shouldShowDemoDataBadge } from "@/lib/demo/detect-synthetic-catalog";

describe("demo isolation", () => {
  it("mock mode does not imply real HTTP API", () => {
    const prev = process.env.NEXT_PUBLIC_ACADEMIC_API_MODE;
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "mock";
    expect(getApiMode()).toBe("mock");
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = prev;
  });

  it("http mode with real courses hides demo badge even if assistant is synthetic", () => {
    expect(
      shouldShowDemoDataBadge(
        "http",
        [{ id: "canvas-99", name: "Real Course", term: "Fall 2026" }],
        { configured: true, provider: "synthetic", available: true },
      ),
    ).toBe(false);
  });

  it("synthetic catalog detection flags demo courses", () => {
    expect(
      isSyntheticCatalog([{ id: "synthetic-1", name: "Demo Course", term: "Demo" }]),
    ).toBe(true);
    expect(shouldShowDemoDataBadge("mock", [], null)).toBe(true);
    expect(shouldShowDemoDataBadge("http", [{ id: "real-1", name: "Real" }], null)).toBe(false);
  });
});
