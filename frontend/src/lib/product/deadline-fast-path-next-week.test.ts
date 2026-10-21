/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildDeadlineFastPathMessage } from "@/lib/product/deadline-fast-path";
import type { Assignment, Course } from "@/lib/domain/types";

describe("next week fast path", () => {
  it("uses backend-provided next week assignments without re-filtering", () => {
    const courses: Course[] = [{ id: "c1", name: "Robotics", code: "CSE 4360" }];
    const nextWeek: Assignment[] = [
      {
        id: "a1",
        courseId: "c1",
        title: "Lab report",
        dueAt: "2026-10-12T17:00:00-05:00",
      },
    ];
    const msg = buildDeadlineFastPathMessage({
      window: "next_week",
      deadlines: { today: [], tomorrow: [], thisWeek: [] },
      overdue: [],
      courses,
      allAssignments: nextWeek,
    });
    expect(msg.text).toContain("Due next week");
    expect(msg.text).toContain("Lab report");
    expect(msg.blocks?.[0]?.content).toBe("next_week");
  });
});
