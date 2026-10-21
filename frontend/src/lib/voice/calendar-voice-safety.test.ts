/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { summarizeBlock } from "@/lib/voice/spoken-summary";

describe("calendar voice safety", () => {
  it("spoken calendar preview requires in-app confirmation", () => {
    const spoken = summarizeBlock({
      type: "calendar_action_preview",
      calendarPreview: {
        event: {
          eventId: "evt-1",
          courseId: "c1",
          assignmentId: "a1",
          summary: "Submit lab report",
          description: null,
          startAt: "2026-10-02T12:00:00Z",
          endAt: "2026-10-02T13:00:00Z",
          allDay: false,
          status: "pending",
          source: "canvas",
          externalId: null,
          provider: "preview",
        },
        confirmation: {
          actionId: "act-secret",
          confirmationToken: "tok-secret",
        },
      },
    });
    expect(spoken.toLowerCase()).toContain("confirm");
    expect(spoken).not.toContain("tok-secret");
    expect(spoken).not.toContain("act-secret");
  });
});
