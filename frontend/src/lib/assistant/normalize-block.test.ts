import { describe, expect, it } from "vitest";
import { sanitizeAssistantBlock } from "@/lib/assistant/normalize-block";

describe("sanitizeAssistantBlock", () => {
  it("passes through known blocks", () => {
    const block = { type: "text" as const, content: "ok" };
    expect(sanitizeAssistantBlock(block)).toEqual(block);
  });

  it("replaces unknown block types with warning", () => {
    const block = { type: "chart" as "text", content: "nope" };
    const safe = sanitizeAssistantBlock(block);
    expect(safe.type).toBe("warning");
    expect(safe.content).toMatch(/unsupported/i);
  });

  it("coerces invalid practice progress values", () => {
    const safe = sanitizeAssistantBlock({
      type: "practice_question",
      practiceSession: {
        sessionId: "p1",
        courseId: "c1",
        topic: "undefined",
        status: "active",
        questionIndex: Number.NaN as unknown as number,
        totalQuestions: 0,
        correctAnswers: 0,
        question: { question: "Q?", generated: true, evidence: [] },
        progress: Number.NaN as unknown as number,
      },
    });
    expect(safe.practiceSession?.progress).toBe(0);
    expect(safe.practiceSession?.topic).toBe("Practice");
  });
});
