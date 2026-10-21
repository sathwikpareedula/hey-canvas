/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";

describe("buildHeyCanvasUrl", () => {
  it("includes course and prompt params", () => {
    const url = buildHeyCanvasUrl({
      courseId: "course-robots",
      prompt: "Help me study",
      assignmentId: "asgn-1",
    });
    expect(url).toContain("courseId=course-robots");
    expect(url).toContain("prompt=");
    expect(url).toContain("assignmentId=asgn-1");
  });

  it("includes study mode", () => {
    const url = buildHeyCanvasUrl({ studyMode: "exam", prompt: "Review" });
    expect(url).toContain("studyMode=exam");
  });
});
