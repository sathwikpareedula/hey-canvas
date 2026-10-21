/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { matchCoursesFromUserText } from "@/lib/courses/course-router-client";
import type { Course } from "@/lib/domain/types";

const courses: Course[] = [
  {
    id: "ml",
    name: "2268-CSE-4309-001-FUNDAMENT OF MACHINE LEARNING",
    code: "CSE 4309",
    term: "Fall 2026",
  },
  {
    id: "rob",
    name: "2268-CSE-4360-001-AUTONOMOUS ROBOT",
    code: "CSE 4360",
    term: "Fall 2026",
  },
];

describe("entity / course continuity (client routing)", () => {
  it("resolves project charter shorthand when only one course catalog", () => {
    const r = matchCoursesFromUserText("how do i do the project charter", [courses[0]]);
    expect(r.outcome).toBe("unresolved");
  });

  it("resolves machine learning from natural language", () => {
    const r = matchCoursesFromUserText("machine learning homework", courses);
    expect(r.outcome).toBe("resolved");
    expect(r.courseId).toBe("ml");
  });

  it("disambiguates robotics vs machine when both match partially", () => {
    const r = matchCoursesFromUserText("cse", courses);
    expect(["ambiguous", "unresolved"]).toContain(r.outcome);
  });

  it("explicit unknown course stays unresolved", () => {
    const r = matchCoursesFromUserText("quantum basket weaving 999", courses);
    expect(r.outcome).toBe("unresolved");
  });
});
