/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  isPracticeSessionCompleteBlock,
  shouldClearActivePracticeSession,
} from "@/lib/assistant/practice-session-state";

describe("practice-session-state", () => {
  it("detects completed practice feedback", () => {
    expect(
      isPracticeSessionCompleteBlock({
        type: "practice_feedback",
        practiceFeedback: {
          correct: true,
          feedback: "Nice work.",
          hint: null,
          nextQuestion: null,
          progress: 100,
        },
      }),
    ).toBe(true);
  });

  it("keeps session active when next question exists", () => {
    expect(
      shouldClearActivePracticeSession([
        {
          type: "practice_feedback",
          practiceFeedback: {
            correct: true,
            feedback: "Good.",
            hint: null,
            nextQuestion: { question: "Next?", generated: true, evidence: [] },
            progress: 50,
          },
        },
      ]),
    ).toBe(false);
  });
});
