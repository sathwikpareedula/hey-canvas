/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  buildDeadlineFastPathMessage,
  matchDeadlineFastPath,
} from "@/lib/product/deadline-fast-path";

describe("deadline fast path", () => {
  it("matches common due-today prompts", () => {
    expect(matchDeadlineFastPath("What do I have due today?")).toBe("today");
    expect(matchDeadlineFastPath("anything due tomorrow?")).toBe("tomorrow");
    expect(matchDeadlineFastPath("what is overdue")).toBe("overdue");
    expect(matchDeadlineFastPath("whats due for next week")).toBe("next_week");
    expect(matchDeadlineFastPath("what is due this week")).toBe("this_week");
    expect(matchDeadlineFastPath("what i got tmrw")).toBe("tomorrow");
    expect(matchDeadlineFastPath("anything next wk")).toBe("next_week");
    expect(matchDeadlineFastPath("am i missing anything?")).toBe("overdue");
    expect(matchDeadlineFastPath("what should i do first?")).toBe("priorities");
  });

  it("orders priorities overdue then soonest due", () => {
    const msg = buildDeadlineFastPathMessage({
      window: "priorities",
      deadlines: {
        today: [
          {
            id: "t1",
            courseId: "c1",
            title: "Today item",
            dueAt: "2026-10-04T23:59:00Z",
          },
        ],
        tomorrow: [],
        thisWeek: [],
      },
      overdue: [
        {
          id: "o1",
          courseId: "c1",
          title: "Late item",
          dueAt: "2026-10-01T23:59:00Z",
        },
      ],
      courses: [{ id: "c1", name: "Course", code: "CSE", term: "2268" }],
    });
    const text = msg.text ?? "";
    expect(text).toContain("What to do first");
    expect(text.indexOf("Late item")).toBeLessThan(text.indexOf("Today item"));
  });

  it("builds empty today message", () => {
    const msg = buildDeadlineFastPathMessage({
      window: "today",
      deadlines: { today: [], tomorrow: [], thisWeek: [] },
      overdue: [],
      courses: [],
    });
    expect(msg.text).toContain("Nothing due today");
  });
});
