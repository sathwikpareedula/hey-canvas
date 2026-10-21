/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildStudentProfile } from "@/lib/acceptance/student-profiles";
import { buildDeadlineFastPathMessage } from "@/lib/product/deadline-fast-path";
import { sanitizeFocusAndPoliciesForCatalog } from "@/lib/product/catalog-sanitize";

describe("tenancy / ownership isolation (single-device profiles)", () => {
  it("user A focus and policies do not include user B course ids after sanitize", () => {
    const userA = buildStudentProfile("three_active_courses", 0);
    const userB = buildStudentProfile("five_active_courses", 1);

    const pollutedFocus = [...userA.focusCourseIds, userB.catalog[0]!.id];
    const policies = {
      [userA.catalog[0]!.id]: {
        instructorPolicy: "unknown" as const,
        cloudProcessing: "local_only" as const,
        notes: "A",
      },
      [userB.catalog[0]!.id]: {
        instructorPolicy: "unknown" as const,
        cloudProcessing: "local_only" as const,
        notes: "B",
      },
    };

    const cleaned = sanitizeFocusAndPoliciesForCatalog(pollutedFocus, userA.catalog, policies);
    expect(cleaned.focusCourseIds).not.toContain(userB.catalog[0]!.id);
    expect(Object.keys(cleaned.policies)).not.toContain(userB.catalog[0]!.id);
    expect(cleaned.focusCourseIds.every((id) => userA.catalog.some((c) => c.id === id))).toBe(true);
  });

  it("course-scoped deadline blocks never include another course's assignments", () => {
    const profile = buildStudentProfile("eight_active_courses", 0);
    const courseA = profile.catalog[0]!;
    const courseB = profile.catalog[1]!;
    const msg = buildDeadlineFastPathMessage({
      window: "priorities",
      deadlines: profile.deadlines,
      overdue: profile.overdue,
      courseId: courseA.id,
      courses: profile.catalog,
    });
    const block = msg.blocks?.[0];
    const assignments =
      block && "assignments" in block ? (block.assignments ?? []) : [];
    for (const a of assignments) {
      expect(a.courseId).toBe(courseA.id);
      expect(a.courseId).not.toBe(courseB.id);
    }
  });

  it("orphan course policy keys are dropped when catalog changes", () => {
    const profile = buildStudentProfile("canvas_course_disappeared", 0);
    const { policies } = sanitizeFocusAndPoliciesForCatalog(
      profile.focusCourseIds,
      profile.catalog,
      {
        "orphan-course": {
          instructorPolicy: "unknown",
          cloudProcessing: "local_only",
          notes: "stale",
        },
        [profile.catalog[0]?.id ?? "x"]: {
          instructorPolicy: "unknown",
          cloudProcessing: "local_only",
          notes: "ok",
        },
      },
    );
    expect(policies["orphan-course"]).toBeUndefined();
  });
});
