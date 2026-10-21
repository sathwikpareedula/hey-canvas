/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildHeyCanvasSuggestions } from "@/lib/hey-canvas/suggestions";

describe("buildHeyCanvasSuggestions", () => {
  it("returns global starters without context", () => {
    const prompts = buildHeyCanvasSuggestions({});
    expect(prompts[0]).toMatch(/due today/i);
    expect(prompts.some((p) => /tomorrow/i.test(p))).toBe(true);
  });

  it("scopes to assignment intents", () => {
    const prompts = buildHeyCanvasSuggestions({
      assignmentId: "a1",
      assignmentTitle: "Lab 2",
    });
    expect(prompts.some((p) => /Lab 2/.test(p) && /explain/i.test(p))).toBe(true);
    expect(prompts.some((p) => /need to know/i.test(p))).toBe(true);
  });

  it("scopes to material intents", () => {
    const prompts = buildHeyCanvasSuggestions({
      documentId: "d1",
      documentTitle: "Lecture 4",
      studyMode: "learn",
    });
    expect(prompts[0]).toMatch(/Teach me/i);
    expect(prompts.some((p) => /Quiz me/i.test(p))).toBe(true);
  });

  it("adds exam prep flavor for course context", () => {
    const prompts = buildHeyCanvasSuggestions({
      courseId: "c1",
      courseName: "Robotics",
      studyMode: "exam",
    });
    expect(prompts[0]).toMatch(/prepare for my next exam/i);
  });
});
