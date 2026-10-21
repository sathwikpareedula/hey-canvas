/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildStudentProfile } from "@/lib/acceptance/student-profiles";
import { focusRolloverHint } from "@/lib/product/focus-courses";

describe("semester rollover", () => {
  it("surfaces a hint when saved term disagrees with catalog", () => {
    const profile = buildStudentProfile("term_changes", 0);
    const hint = focusRolloverHint(
      {
        version: 1,
        focusCourseIds: profile.focusCourseIds,
        termHint: profile.termHint,
        updatedAt: new Date(0).toISOString(),
      },
      profile.catalog,
    );
    expect(hint).toMatch(/review Focus Courses/i);
  });

  it("explains when focus courses vanished from catalog", () => {
    const profile = buildStudentProfile("canvas_course_disappeared", 0);
    const hint = focusRolloverHint(
      {
        version: 1,
        focusCourseIds: ["course-removed-by-canvas"],
        termHint: null,
        updatedAt: new Date(0).toISOString(),
      },
      profile.catalog,
    );
    expect(hint).toMatch(/none of your saved focus courses/i);
  });
});
