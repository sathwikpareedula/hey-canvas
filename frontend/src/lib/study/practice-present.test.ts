/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { practiceProgressLabel } from "@/lib/study/practice-present";

describe("practiceProgressLabel", () => {
  it("never includes NaN", () => {
    const label = practiceProgressLabel({
      sessionId: "p1",
      courseId: "c1",
      topic: "x",
      status: "active",
      questionIndex: Number.NaN as unknown as number,
      totalQuestions: undefined as unknown as number,
      correctAnswers: 0,
      question: null,
      progress: Number.NaN as unknown as number,
    });
    expect(label).not.toMatch(/NaN/);
    expect(label).toMatch(/Question 1 of 1/);
  });
});
