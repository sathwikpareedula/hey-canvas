/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import type { Course } from "@/lib/domain/types";
import { matchCoursesFromUserText } from "@/lib/courses/course-router-client";

function course(id: string, name: string, code?: string): Course {
  return {
    id,
    name,
    code: code ?? "",
    term: "Fall 2026",
  };
}

describe("course-router-client fuzzy match", () => {
  const catalog = [
    course("1", "Synthetic Autonomous Robots", "CSE 4360"),
    course("2", "Synthetic Neural Networks", "CSE 4309"),
    course("3", "Senior Design Project I", "CSE 4380"),
  ];

  it("resolves common nicknames and light misspellings", () => {
    expect(matchCoursesFromUserText("help me study robotics", catalog).outcome).toBe("resolved");
    expect(matchCoursesFromUserText("robotcs homework", catalog).courseId).toBe("1");
    expect(matchCoursesFromUserText("neurel networks quiz", catalog).courseId).toBe("2");
    expect(matchCoursesFromUserText("senor design", catalog).courseId).toBe("3");
  });

  it("stays ambiguous when multiple courses match equally", () => {
    const crowded = [course("a", "Robotics Alpha"), course("b", "Robotics Beta")];
    expect(matchCoursesFromUserText("robotics", crowded).outcome).toBe("ambiguous");
  });
});
