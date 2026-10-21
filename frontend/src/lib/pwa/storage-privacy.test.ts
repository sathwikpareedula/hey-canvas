/**
 * @vitest-environment node
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("storage and PWA privacy", () => {
  it("service worker does not cache API routes", () => {
    const swPath = resolve(process.cwd(), "public/sw.js");
    const source = readFileSync(swPath, "utf8");
    expect(source).toContain('pathname.startsWith("/api")');
    expect(source).not.toMatch(/cache\.put\([^)]*\/api/);
  });

  it("documents expected localStorage keys only", () => {
    const keys = [
      "hey-canvas-preferences",
      "hey-canvas-study-session-id",
      "hey-canvas-practice-session-id",
      "hey-canvas-onboarding-v1",
      "hey-canvas-focus-courses-v1",
      "hey-canvas-ai-preferences-v1",
      "hey-canvas-course-ai-policies-v1",
      "hey-canvas-product-migrated-v1",
    ];
    const forbidden = ["password", "secret", "confirmation", "credential", "oauth"];
    for (const key of keys) {
      const lower = key.toLowerCase();
      for (const word of forbidden) {
        expect(lower.includes(word)).toBe(false);
      }
    }
  });
});
