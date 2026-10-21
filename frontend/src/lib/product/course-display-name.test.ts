import { describe, expect, it } from "vitest";

import { courseDisplayName, courseNavLabel } from "@/lib/product/course-display-name";

describe("course display names", () => {
  const canvasCourse = {
    id: "course-1",
    name: "2268-CSE-4309-001-FUNDAMENTALS OF MACHINE LEARNING",
    code: "2268-CSE-4309-001",
  };

  it("uses a human title as the primary sidebar label", () => {
    expect(courseDisplayName(canvasCourse)).toBe(
      "Fundamentals Of Machine Learning (2268-CSE-4309-001)",
    );
    expect(courseNavLabel(canvasCourse)).toBe("Fundamentals Of Machine Learning (2268-…");
  });

  it("keeps an explicit student-facing profile alias authoritative", () => {
    expect(
      courseDisplayName(canvasCourse, {
        courseId: canvasCourse.id,
        courseName: canvasCourse.name,
        courseCode: canvasCourse.code,
        hasCustomProfile: true,
        profile: {
          displayAlias: "Machine Learning",
          shortLabel: null,
          description: null,
          terminologyNotes: null,
          studyInstructions: null,
          enabled: true,
          teachingDepth: "balanced",
          startingLevel: "course_context",
          explanationStyle: "concept_first",
          answerStyle: "balanced",
          stepByStep: null,
          examStyle: false,
          visualPreference: "auto",
          mathDetail: "auto",
          codeDetail: "auto",
        },
        effectivePreferences: {
          teachingDepth: "balanced",
          startingLevel: "course_context",
          explanationStyle: "concept_first",
          answerStyle: "balanced",
          stepByStep: null,
          examStyle: false,
          visualPreference: "auto",
          mathDetail: "auto",
          codeDetail: "auto",
        },
        effectiveCourseInstructions: null,
        updatedAt: null,
      }),
    ).toBe("Machine Learning");
  });
});
