/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapCourseProfile,
  mapCourseRoutingResult,
} from "@/lib/api/http/course-profile-adapters";

describe("course profile adapters", () => {
  it("maps course profile view", () => {
    const profile = mapCourseProfile({
      course_id: "c-1",
      course_name: "Robotics",
      course_code: "EE",
      has_custom_profile: true,
      profile: null,
      effective_preferences: {
        teaching_depth: "balanced",
        starting_level: "course_context",
        explanation_style: "step_by_step",
        answer_style: "balanced",
        step_by_step: true,
        exam_style: false,
        visual_preference: "auto",
        math_detail: "auto",
        code_detail: "auto",
      },
      effective_course_instructions: "Be concise.",
      created_at: null,
      updated_at: null,
    });
    expect(profile.courseId).toBe("c-1");
    expect(profile.effectivePreferences.stepByStep).toBe(true);
  });

  it("maps ambiguous routing", () => {
    const result = mapCourseRoutingResult({
      outcome: "ambiguous",
      course: null,
      evidence: [],
      candidates: [
        { course_id: "a", course_name: "A", course_code: null },
        { course_id: "b", course_name: "B", course_code: null },
      ],
      reason: "Multiple matches",
    });
    expect(result.outcome).toBe("ambiguous");
    expect(result.candidates).toHaveLength(2);
  });
});
