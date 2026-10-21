/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { presentAcademicError } from "@/lib/api/error-presentation";
import { AcademicApiNotFoundError } from "@/lib/api/errors";

describe("presentAcademicError", () => {
  it("treats missing study session as actionable", () => {
    const presented = presentAcademicError(new AcademicApiNotFoundError("Study session"));
    expect(presented.title).toBe("No saved session");
    expect(presented.retryable).toBe(false);
  });

  it("surfaces choose-course messages without scary generic copy", () => {
    const presented = presentAcademicError(new Error("Choose a course before starting."));
    expect(presented.title).toBe("Action needed");
    expect(presented.message).toContain("Choose a course");
  });
});
