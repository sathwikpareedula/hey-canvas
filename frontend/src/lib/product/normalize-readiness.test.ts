/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { normalizeProductReadiness } from "@/lib/product/normalize-readiness";

describe("normalizeProductReadiness", () => {
  it("dedupes duplicate database checks", () => {
    const out = normalizeProductReadiness({
      overall: "unknown",
      updatedAt: null,
      checks: [
        {
          component: "database",
          status: "unknown",
          label: "Local database",
          detail: null,
          actionLabel: null,
        },
        {
          component: "database",
          status: "ready",
          label: "Database",
          detail: null,
          actionLabel: null,
        },
      ],
    });
    expect(out.checks.filter((c) => c.component === "database")).toHaveLength(1);
    expect(out.checks.find((c) => c.component === "database")?.status).toBe("ready");
  });

  it("enriches unknown sync from probe", () => {
    const out = normalizeProductReadiness(
      {
        overall: "unknown",
        updatedAt: null,
        checks: [
          {
            component: "sync",
            status: "unknown",
            label: "Sync",
            detail: null,
            actionLabel: null,
          },
        ],
      },
      { syncProbe: { hasSync: true, status: "ok", relativeLabel: "3d ago" } },
    );
    expect(out.checks[0]?.detail).toContain("3d ago");
  });
});
