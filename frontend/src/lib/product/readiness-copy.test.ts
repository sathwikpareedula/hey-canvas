/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapAssistantStatusToReadiness,
  readinessStatusStudentLine,
  sanitizeReadinessDetail,
} from "@/lib/product/readiness-copy";

describe("readiness copy", () => {
  it("strips internal details", () => {
    expect(sanitizeReadinessDetail("Traceback (most recent call last)")).toBeNull();
    expect(sanitizeReadinessDetail("failed at http://127.0.0.1:11434")).toBeNull();
    expect(sanitizeReadinessDetail("Canvas connected")).toBe("Canvas connected");
  });

  it("maps ollama unavailable", () => {
    const checks = mapAssistantStatusToReadiness(true, "ollama", false);
    expect(checks.some((c) => c.component === "local_ai_runtime")).toBe(true);
  });

  it("student lines for canvas degraded", () => {
    expect(readinessStatusStudentLine("canvas", "degraded")).toContain("synced");
  });
});
