/**
 * @vitest-environment node
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const root = path.resolve(import.meta.dirname, "..", "..");

describe("wake word integration surfaces", () => {
  it("wires hands-free hook in course chat and general workspace", () => {
    const course = readFileSync(
      path.join(root, "components/courses/CourseChatPanel.tsx"),
      "utf8",
    );
    const workspace = readFileSync(
      path.join(root, "components/hey-canvas/HeyCanvasWorkspace.tsx"),
      "utf8",
    );
    expect(course).toContain("useHeyCanvasWakeWord");
    expect(course).toContain("notifySpeaking");
    expect(course).toMatch(/voiceInput\.phase === "processing"/);
    expect(workspace).toContain("useHeyCanvasWakeWord");
    expect(workspace).toContain("notifySpeaking");
    expect(workspace).toMatch(/voiceInput\.phase === "processing"/);
  });
});
