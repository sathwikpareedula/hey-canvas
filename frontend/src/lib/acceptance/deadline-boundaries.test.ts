/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import type { Assignment } from "@/lib/domain/types";
import {
  filterAssignmentsForNextWeek,
  isNextChicagoCalendarWeek,
  pickNextDeadline,
} from "@/lib/assignments/deadline-selection";
import { matchDeadlineFastPath } from "@/lib/product/deadline-fast-path";

function a(id: string, dueAt: string): Assignment {
  return { id, courseId: "c", title: id, dueAt };
}

describe("deadline boundaries (America/Chicago)", () => {
  it("next week prompt does not match this week", () => {
    expect(matchDeadlineFastPath("whats due for next week")).toBe("next_week");
    expect(matchDeadlineFastPath("what is due this week")).toBe("this_week");
  });

  it("Sunday/Monday week boundary", () => {
    const sunday = new Date("2026-10-04T15:00:00.000Z");
    expect(isNextChicagoCalendarWeek("2026-10-12T23:59:00-05:00", sunday)).toBe(true);
    expect(isNextChicagoCalendarWeek("2026-10-04T23:59:00-05:00", sunday)).toBe(false);
  });

  it("month boundary next week", () => {
    const now = new Date("2026-09-28T18:00:00.000Z");
    const next = filterAssignmentsForNextWeek(
      [a("oct", "2026-10-05T12:00:00-05:00"), a("sep", "2026-09-29T12:00:00-05:00")],
      now,
    );
    expect(next.map((x) => x.id)).toEqual(["oct"]);
  });

  it("past does not win next deadline", () => {
    const now = new Date("2026-10-03T18:00:00.000Z");
    const next = pickNextDeadline(
      [a("past", "2026-08-28T23:59:00-05:00"), a("future", "2026-12-01T23:59:00-06:00")],
      now,
    );
    expect(next?.id).toBe("future");
  });

  it("no due date does not become next deadline", () => {
    const now = new Date("2026-10-03T18:00:00.000Z");
    expect(pickNextDeadline([a("nodate", ""), a("dated", "2026-10-10T12:00:00-05:00")], now)?.id).toBe(
      "dated",
    );
  });
});
