/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { practiceAnswerRequest, practiceHintRequest } from "@/lib/assistant/practice-chat";

describe("practice-chat requests", () => {
  it("builds hint request with session id", () => {
    const req = practiceHintRequest("practice:abc");
    expect(req.practiceSessionId).toBe("practice:abc");
    expect(req.prompt.toLowerCase()).toContain("hint");
  });

  it("builds answer request with answer field", () => {
    const req = practiceAnswerRequest("practice:abc", "My substantive answer here.");
    expect(req.practiceSessionId).toBe("practice:abc");
    expect(req.answer).toBe("My substantive answer here.");
    expect(req.prompt.toLowerCase()).toContain("check");
  });
});
