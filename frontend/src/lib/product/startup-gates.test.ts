/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import type { ProductReadiness } from "@/lib/domain/product-settings";
import { localAiBlocksStartup } from "@/lib/product/startup-gates";

function readiness(
  checks: ProductReadiness["checks"],
  overall: ProductReadiness["overall"] = "degraded",
): ProductReadiness {
  return { overall, checks, updatedAt: new Date().toISOString() };
}

describe("localAiBlocksStartup", () => {
  it("cloud mode never blocks", () => {
    expect(
      localAiBlocksStartup(
        readiness([
          { component: "local_ai_runtime", status: "unavailable", label: "", detail: null, actionLabel: null },
        ]),
        "cloud",
      ),
    ).toBe(false);
  });

  it("blocks when runtime unavailable in local mode", () => {
    expect(
      localAiBlocksStartup(
        readiness([
          { component: "local_ai_runtime", status: "unavailable", label: "", detail: null, actionLabel: null },
        ]),
        "local",
      ),
    ).toBe(true);
  });

  it("blocks when model action required", () => {
    expect(
      localAiBlocksStartup(
        readiness([
          { component: "local_ai_runtime", status: "ready", label: "", detail: null, actionLabel: null },
          { component: "local_ai_model", status: "action_required", label: "", detail: null, actionLabel: null },
        ]),
        "local",
      ),
    ).toBe(true);
  });

  it("does not block on degraded runtime alone", () => {
    expect(
      localAiBlocksStartup(
        readiness([
          { component: "local_ai_runtime", status: "degraded", label: "", detail: null, actionLabel: null },
          { component: "local_ai_model", status: "ready", label: "", detail: null, actionLabel: null },
        ]),
        "local",
      ),
    ).toBe(false);
  });
});
