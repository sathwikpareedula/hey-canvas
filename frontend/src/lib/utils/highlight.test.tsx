/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { splitHighlight } from "@/lib/utils/highlight";

describe("splitHighlight", () => {
  it("marks matching segments", () => {
    const parts = splitHighlight("inverse kinematics sample", "kinematics");
    expect(parts.some((p) => p.match && p.text === "kinematics")).toBe(true);
  });

  it("does not inject HTML", () => {
    const parts = splitHighlight("<script>alert(1)</script>", "script");
    expect(parts.every((p) => !p.text.includes("<"))).toBe(false);
    expect(JSON.stringify(parts)).not.toContain("&lt;");
  });
});
