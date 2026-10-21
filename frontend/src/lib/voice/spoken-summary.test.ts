/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { summarizeBlock, summarizeMessageForSpeech } from "@/lib/voice/spoken-summary";

describe("spoken-summary", () => {
  it("summarizes deadlines without ids", () => {
    const text = summarizeBlock({
      type: "deadlines",
      assignments: [
        {
          id: "secret-id",
          courseId: "c1",
          title: "Homework 2",
          dueAt: "2026-10-02T00:00:00Z",
        },
      ],
    });
    expect(text).toContain("Homework 2");
    expect(text).not.toContain("secret-id");
  });

  it("calendar preview mentions confirmation", () => {
    const text = summarizeBlock({
      type: "calendar_action_preview",
      calendarPreview: {
        event: {
          eventId: "e1",
          courseId: "c1",
          assignmentId: "a1",
          summary: "Submit lab",
          description: null,
          startAt: "2026-10-02T12:00:00Z",
          endAt: "2026-10-02T13:00:00Z",
          allDay: false,
          status: "pending",
          source: "canvas",
          externalId: null,
          provider: "preview",
        },
        confirmation: { actionId: "act", confirmationToken: "tok" },
      },
    });
    expect(text.toLowerCase()).toContain("confirm");
    expect(text).not.toContain("tok");
  });

  it("strips practice session ids from speech", () => {
    const text = summarizeBlock({
      type: "text",
      content: "Resume practice:practice:abc123def for course work.",
    });
    expect(text).not.toContain("practice:abc");
  });

  it("summarizes assistant message blocks", () => {
    const text = summarizeMessageForSpeech({
      id: "1",
      role: "assistant",
      createdAt: new Date().toISOString(),
      blocks: [{ type: "text", content: "Hello there." }],
    });
    expect(text).toBe("Hello there.");
  });
});
