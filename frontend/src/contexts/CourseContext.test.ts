/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildCourseContextUrl } from "@/contexts/CourseContext";

describe("buildCourseContextUrl", () => {
  it("keeps the current route and preserves other query params when updating course context", () => {
    const url = buildCourseContextUrl(
      "/materials",
      new URLSearchParams("q=robot&sort=recent"),
      "course-42",
    );

    expect(url).toBe("/materials?q=robot&sort=recent&courseId=course-42");
  });

  it("removes the courseId while leaving unrelated query params intact", () => {
    const url = buildCourseContextUrl(
      "/assignments",
      new URLSearchParams("courseId=course-42&window=today"),
      null,
    );

    expect(url).toBe("/assignments?window=today");
  });
});
