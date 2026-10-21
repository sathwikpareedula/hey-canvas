/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapBackendAssistantResponseToChatMessage,
  mapBackendResponseBlock,
  mapTransportRequestToBackendBody,
  mapUiStudyModeToAssistantBackend,
} from "@/lib/api/http/assistant-adapters";
import { ASSISTANT_EMPTY_RECOVERY_MESSAGE } from "@/lib/assistant/empty-response";

describe("assistant backend request mapping", () => {
  it("maps session and study mode fields", () => {
    const body = mapTransportRequestToBackendBody({
      query: "What's due?",
      courseId: "c1",
      conversationId: "conv-1",
      assignmentId: "a1",
      documentId: "d1",
      backendStudyMode: "exam_prep",
    });
    expect(body).toEqual({
      query: "What's due?",
      course_id: "c1",
      session_id: "conv-1",
      assignment_id: "a1",
      document_id: "d1",
      study_mode: "exam_prep",
      operation: "answer",
    });
  });

  it("maps practice session fields", () => {
    const body = mapTransportRequestToBackendBody({
      query: "check my answer",
      practiceSessionId: "practice:1",
      answer: "My long answer text here.",
      operation: "answer",
    });
    expect(body.practice_session_id).toBe("practice:1");
    expect(body.answer).toBe("My long answer text here.");
  });

  it("maps UI exam mode to exam_prep", () => {
    expect(mapUiStudyModeToAssistantBackend("exam")).toBe("exam_prep");
    expect(mapUiStudyModeToAssistantBackend("learn")).toBe("learn");
  });

  it("maps empty backend response to recovery message", () => {
    const msg = mapBackendAssistantResponseToChatMessage({ status: "ok", blocks: [] });
    expect(msg.blocks?.[0]?.type).toBe("error");
    expect(msg.blocks?.[0]?.content).toBe(ASSISTANT_EMPTY_RECOVERY_MESSAGE);
  });

  it("maps deadline_group window hint from payload", () => {
    const block = mapBackendResponseBlock({
      type: "deadline_group",
      text: "ignored when window present",
      payload: { window: "tomorrow", assignments: [] },
    });
    expect(block?.type).toBe("deadlines");
    expect(block?.content).toBe("tomorrow");
  });
});
