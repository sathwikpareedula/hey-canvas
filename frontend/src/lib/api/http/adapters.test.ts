/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { AcademicApiMalformedError } from "@/lib/api/errors";
import { mapSyncRun } from "@/lib/api/http/adapters";

describe("mapSyncRun", () => {
  it("maps a valid sync run row", () => {
    const run = mapSyncRun({
      id: 1,
      started_at: "2026-01-01T00:00:00Z",
      finished_at: null,
      status: "succeeded",
      trigger: "cli",
      change_events_created: 2,
      error_count: 0,
    });
    expect(run.id).toBe(1);
    expect(run.status).toBe("succeeded");
  });

  it("throws on invalid status", () => {
    expect(() =>
      mapSyncRun({
        id: 1,
        started_at: "2026-01-01T00:00:00Z",
        finished_at: null,
        status: "completed",
        trigger: "cli",
        change_events_created: 0,
        error_count: 0,
      } as never),
    ).toThrow(AcademicApiMalformedError);
  });
});
