/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { sanitizeFocusAndPoliciesForCatalog } from "@/lib/product/catalog-sanitize";

describe("catalog sanitize", () => {
  it("removes stale focus ids and orphan policies", () => {
    const catalog = [{ id: "c1", name: "One", term: "Fall 2026" }];
    const result = sanitizeFocusAndPoliciesForCatalog(
      ["c1", "gone"],
      catalog,
      {
        c1: { instructorPolicy: "unknown", cloudProcessing: "local_only", notes: "" },
        gone: { instructorPolicy: "unknown", cloudProcessing: "local_only", notes: "x" },
      },
    );
    expect(result.focusCourseIds).toEqual(["c1"]);
    expect(Object.keys(result.policies)).toEqual(["c1"]);
  });
});
