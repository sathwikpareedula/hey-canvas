/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapBackendStudyGuide,
  mapBackendStudySession,
  mapStudySessionCreateToBackend,
} from "@/lib/api/http/study-workflow-adapters";

describe("study workflow adapters", () => {
  it("maps study session create body", () => {
    expect(
      mapStudySessionCreateToBackend({
        courseId: "c1",
        goal: "Learn",
        durationMinutes: 30,
        topics: ["Topic"],
        studyMode: "learn",
        assignmentIds: ["a1"],
      }),
    ).toEqual({
      course_id: "c1",
      goal: "Learn",
      duration_minutes: 30,
      topics: ["Topic"],
      study_mode: "learn",
      assignment_ids: ["a1"],
    });
  });

  it("maps camelCase partial study session without NaN fields", () => {
    const session = mapBackendStudySession({
      sessionId: "s2",
      courseId: "c1",
      studyMode: "exam_prep",
      status: "active",
      steps: [],
    });
    expect(session.goal).toBe("Study plan");
    expect(session.durationMinutes).toBe(45);
    expect(Number.isNaN(session.progress)).toBe(false);
  });

  it("maps study session view", () => {
    const session = mapBackendStudySession({
      session_id: "s1",
      course_id: "c1",
      goal: "Review",
      duration_minutes: 45,
      topics: [],
      study_mode: "review",
      assignment_ids: [],
      status: "active",
      relevant_evidence: [],
      steps: [{ order: 1, title: "Step", minutes: 10, status: "pending" }],
      progress: 0,
    });
    expect(session.sessionId).toBe("s1");
    expect(session.steps[0]?.title).toBe("Step");
  });

  it("maps study guide", () => {
    const guide = mapBackendStudyGuide({
      title: "Guide",
      scope: "Unit 2",
      key_concepts: ["A"],
      explanations: ["B"],
      evidence: [{ authority: "professor_material", identifier: "f1" }],
      review_checklist: ["Read"],
      practice_prompts: ["Try"],
      uncertainties: ["Maybe"],
    });
    expect(guide.keyConcepts).toEqual(["A"]);
    expect(guide.evidence[0]?.identifier).toBe("f1");
  });
});
