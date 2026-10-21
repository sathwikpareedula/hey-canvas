/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  extractPracticeSessionIdFromBlocks,
  mapStructuredAssistantBlock,
} from "@/lib/api/http/assistant-structured-blocks";
import { mapBackendResponseBlock } from "@/lib/api/http/assistant-adapters";

describe("structured assistant blocks", () => {
  it("maps practice_question payload", () => {
    const block = mapStructuredAssistantBlock({
      type: "practice_question",
      payload: {
        session_id: "practice:abc",
        course_id: "c1",
        topic: "forces",
        status: "active",
        question_index: 0,
        total_questions: 3,
        correct_answers: 0,
        progress: 0,
        question: {
          question: "Explain forces.",
          generated: true,
          evidence: [],
        },
      },
    });
    expect(block?.type).toBe("practice_question");
    expect(block?.practiceSession?.sessionId).toBe("practice:abc");
  });

  it("maps study_plan nested session payload", () => {
    const block = mapStructuredAssistantBlock({
      type: "study_plan",
      payload: {
        study_session: {
          session_id: "study:2",
          course_id: "c1",
          goal: "Exam prep",
          duration_minutes: 30,
          topics: ["Unit 1"],
          study_mode: "exam_prep",
          assignment_ids: [],
          status: "active",
          relevant_evidence: [],
          steps: [{ order: 1, title: "Review", minutes: 20, status: "pending" }],
          progress: 10,
        },
      },
    });
    expect(block?.studySession?.goal).toBe("Exam prep");
    expect(block?.studySession?.durationMinutes).toBe(30);
  });

  it("maps study_plan StudySessionView payload", () => {
    const block = mapBackendResponseBlock({
      type: "study_plan",
      payload: {
        session_id: "study:1",
        course_id: "c1",
        goal: "Review midterm",
        duration_minutes: 45,
        topics: ["Chapter 3"],
        study_mode: "learn",
        assignment_ids: [],
        status: "active",
        relevant_evidence: [],
        steps: [{ order: 1, title: "Skim notes", minutes: 15, status: "pending" }],
        progress: 0,
      },
    });
    expect(block?.type).toBe("study_plan");
    expect(block?.studySession?.steps[0]?.title).toBe("Skim notes");
  });

  it("extracts practice session id from blocks", () => {
    const id = extractPracticeSessionIdFromBlocks([
      { type: "text", content: "hi" },
      {
        type: "practice_question",
        practiceSession: {
          sessionId: "practice:xyz",
          courseId: "c1",
          topic: "t",
          status: "active",
          questionIndex: 0,
          totalQuestions: 2,
          correctAnswers: 0,
          question: null,
          progress: 0,
        },
      },
    ]);
    expect(id).toBe("practice:xyz");
  });
});
