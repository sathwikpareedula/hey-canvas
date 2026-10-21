/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { MockAcademicApi } from "@/lib/api/mock-academic-api";

describe("MockAcademicApi", () => {
  const api = new MockAcademicApi();

  it("filters assignments by window", async () => {
    const today = await api.getAssignments({ window: "today" });
    expect(today.length).toBeGreaterThan(0);
    expect(today.every((a) => a.deadlineWindow === "today")).toBe(true);
  });

  it("returns document search matches for kinematics", async () => {
    const results = await api.searchDocuments({ query: "kinematics" });
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].snippet.toLowerCase()).toContain("kinematics");
  });

  it("askAssistant handles due today prompt", async () => {
    const msg = await api.askAssistant("What's due today?");
    expect(msg.role).toBe("assistant");
    expect(msg.blocks?.some((b) => b.type === "deadlines")).toBe(true);
  });

  it("grounds the synthetic Quiz 3 plan in labeled sample sources", async () => {
    const msg = await api.askAssistant(
      "Help me prepare for Quiz 3 using the syllabus, announcements, and lecture materials.",
      "course-robots",
    );
    const rendered = JSON.stringify(msg);
    expect(rendered).toContain("Quiz 3 preparation plan (demo)");
    expect(rendered).toContain("synthetic sample sources");
    expect(msg.blocks?.some((block) => block.type === "document_answer")).toBe(true);
  });
});
