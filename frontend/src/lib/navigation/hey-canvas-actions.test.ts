/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  assignmentHeyCanvasActions,
  heyCanvasActionHref,
  materialHeyCanvasActions,
} from "@/lib/navigation/hey-canvas-actions";

describe("hey-canvas-actions", () => {
  it("builds assignment actions with context ids in href", () => {
    const actions = assignmentHeyCanvasActions("Lab 3", {
      assignmentId: "a-1",
      courseId: "c-1",
    });
    const href = heyCanvasActionHref(actions[0], "learn");
    expect(href).toContain("assignmentId=a-1");
    expect(href).toContain("courseId=c-1");
    expect(href).toContain("studyMode=learn");
    expect(href).toContain("prompt=");
  });

  it("builds material actions with document context", () => {
    const actions = materialHeyCanvasActions("Lecture 4 slides", {
      documentId: "doc-1",
      courseId: "c-2",
    });
    const href = heyCanvasActionHref(actions[2], "practice");
    expect(href).toContain("documentId=doc-1");
    expect(href).toContain("studyMode=practice");
  });
});
