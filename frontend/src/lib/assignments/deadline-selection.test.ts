/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import type { Assignment } from "@/lib/domain/types";
import {
  filterAssignmentsForNextWeek,
  filterUpcomingAssignments,
  isDueInFuture,
  pickNextDeadline,
} from "@/lib/assignments/deadline-selection";

const NOW = new Date("2026-10-03T18:00:00.000Z");

function a(id: string, dueAt: string | null, extra?: Partial<Assignment>): Assignment {
  return {
    id,
    courseId: "c1",
    title: id,
    dueAt,
    ...extra,
  };
}

describe("deadline-selection", () => {
  it("excludes past due dates from next deadline", () => {
    const list = [
      a("past", "2026-08-28T23:59:00-05:00"),
      a("future", "2026-10-10T23:59:00-05:00"),
    ];
    expect(pickNextDeadline(list, NOW)?.id).toBe("future");
  });

  it("filters upcoming to future only", () => {
    const list = [
      a("past", "2026-08-28T23:59:00-05:00", { deadlineWindow: "past_due_time" }),
      a("soon", "2026-10-05T12:00:00-05:00"),
    ];
    expect(filterUpcomingAssignments(list, NOW).map((x) => x.id)).toEqual(["soon"]);
  });

  it("next calendar week excludes current week (Chicago)", () => {
    const list = [
      a("this-week", "2026-10-01T23:59:00-05:00"),
      a("next-week", "2026-10-08T23:59:00-05:00"),
    ];
    expect(filterAssignmentsForNextWeek(list, NOW).map((x) => x.id)).toEqual(["next-week"]);
  });

  it("isDueInFuture respects instant", () => {
    expect(isDueInFuture("2026-10-03T19:00:00-05:00", NOW)).toBe(true);
    expect(isDueInFuture("2026-10-01T12:00:00-05:00", NOW)).toBe(false);
  });
});
