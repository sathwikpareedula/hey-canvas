/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { syncStatusIsUnhealthy, syncStatusRecoveryHint } from "@/lib/product/student-sync-recovery";

describe("student sync recovery", () => {
  it("suggests recovery for failed sync", () => {
    const hint = syncStatusRecoveryHint({
      id: 1,
      startedAt: "",
      finishedAt: null,
      status: "failed",
      trigger: "manual",
      changeEventsCreated: 0,
      errorCount: 1,
    });
    expect(hint).toMatch(/Canvas token/i);
    expect(syncStatusIsUnhealthy("failed")).toBe(true);
  });

  it("returns null for healthy sync", () => {
    expect(
      syncStatusRecoveryHint({
        id: 1,
        startedAt: "",
        finishedAt: "",
        status: "succeeded",
        trigger: "manual",
        changeEventsCreated: 2,
        errorCount: 0,
      }),
    ).toBeNull();
  });
});
