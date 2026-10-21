/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { coursePrimaryTitle } from "@/lib/courses/display";

describe("course display", () => {
  it("prefers human title from SIS-style name", () => {
    const title = coursePrimaryTitle({
      name: "2268-CSE-4309-001-FUNDAMENT OF MACHINE LEARNING",
      code: "CSE 4309",
    });
    expect(title.toLowerCase()).toContain("machine");
    expect(title).not.toMatch(/^2268-/);
  });
});
