/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { deadlineWindowLabel } from "@/lib/utils/date";

describe("deadlineWindowLabel", () => {
  it("uses past due time wording", () => {
    expect(deadlineWindowLabel("past_due_time")).toBe("Past due time");
  });

  it("does not imply missing submissions", () => {
    expect(deadlineWindowLabel("past_due_time")).not.toMatch(/missing/i);
  });
});
