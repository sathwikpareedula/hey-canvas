/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { inferEvidenceSourceKind } from "@/lib/evidence/source-kind";

describe("inferEvidenceSourceKind", () => {
  it("classifies professor documents", () => {
    expect(
      inferEvidenceSourceKind({
        courseId: "1",
        courseName: "Robotics",
        documentTitle: "Lecture 3",
      }),
    ).toBe("professor_material");
  });

  it("classifies module items", () => {
    expect(
      inferEvidenceSourceKind({
        courseId: "1",
        courseName: "Robotics",
        moduleName: "Week 2",
        moduleItemTitle: "Reading",
      }),
    ).toBe("module");
  });
});
