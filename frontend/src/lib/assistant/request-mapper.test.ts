import { describe, expect, it } from "vitest";
import { mapUiRequestToTransport } from "@/lib/assistant/request-mapper";

describe("assistant request mapper", () => {
  it("maps prompt to query and preserves session context", () => {
    const mapped = mapUiRequestToTransport({
      prompt: "  What's due?  ",
      courseId: "c1",
      conversationId: "conv-1",
      assignmentId: "a1",
      documentId: "d1",
      studyMode: "exam",
    });
    expect(mapped.query).toBe("What's due?");
    expect(mapped.conversationId).toBe("conv-1");
    expect(mapped.backendStudyMode).toBe("exam_prep");
    expect(
      mapUiRequestToTransport({ prompt: "x", studyMode: "learn" }).backendStudyMode,
    ).toBe("learn");
  });
});
