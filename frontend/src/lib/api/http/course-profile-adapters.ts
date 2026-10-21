import { AcademicApiMalformedError } from "@/lib/api/errors";
import type {
  AcademicContext,
  CourseProfile,
  CourseProfileData,
  CourseRoutingResult,
  CourseStudyPreferences,
  ResolvedCourse,
  StudyContext,
} from "@/lib/domain/course-intelligence";

type BackendPreferences = {
  teaching_depth: string;
  starting_level: string;
  explanation_style: string;
  answer_style: string;
  step_by_step: boolean | null;
  exam_style: boolean;
  visual_preference: string;
  math_detail: string;
  code_detail: string;
};

function mapPreferences(row: BackendPreferences): CourseStudyPreferences {
  return {
    teachingDepth: row.teaching_depth as CourseStudyPreferences["teachingDepth"],
    startingLevel: row.starting_level as CourseStudyPreferences["startingLevel"],
    explanationStyle: row.explanation_style as CourseStudyPreferences["explanationStyle"],
    answerStyle: row.answer_style as CourseStudyPreferences["answerStyle"],
    stepByStep: row.step_by_step,
    examStyle: row.exam_style,
    visualPreference: row.visual_preference as CourseStudyPreferences["visualPreference"],
    mathDetail: row.math_detail as CourseStudyPreferences["mathDetail"],
    codeDetail: row.code_detail as CourseStudyPreferences["codeDetail"],
  };
}

function mapProfileData(row: Record<string, unknown> | null): CourseProfileData | null {
  if (!row) return null;
  const prefs = mapPreferences(row as BackendPreferences);
  return {
    ...prefs,
    displayAlias: (row.display_alias as string | null) ?? null,
    shortLabel: (row.short_label as string | null) ?? null,
    description: (row.description as string | null) ?? null,
    terminologyNotes: (row.terminology_notes as string | null) ?? null,
    studyInstructions: (row.study_instructions as string | null) ?? null,
    enabled: Boolean(row.enabled ?? true),
  };
}

export function mapCourseProfile(row: Record<string, unknown>): CourseProfile {
  if (!row.course_id || typeof row.course_id !== "string") {
    throw new AcademicApiMalformedError("Course profile missing course_id");
  }
  return {
    courseId: row.course_id,
    courseName: (row.course_name as string | null) ?? null,
    courseCode: (row.course_code as string | null) ?? null,
    hasCustomProfile: Boolean(row.has_custom_profile),
    profile: mapProfileData((row.profile as Record<string, unknown>) ?? null),
    effectivePreferences: mapPreferences(
      row.effective_preferences as BackendPreferences,
    ),
    effectiveCourseInstructions:
      (row.effective_course_instructions as string | null) ?? null,
    updatedAt: (row.updated_at as string | null) ?? null,
  };
}

export function mapStudyContext(row: Record<string, unknown>): StudyContext {
  if (!row.course_id || typeof row.course_id !== "string") {
    throw new AcademicApiMalformedError("Study context missing course_id");
  }
  return {
    courseId: row.course_id,
    courseName: (row.course_name as string | null) ?? null,
    hasContext: Boolean(row.has_context),
    currentTopic: (row.current_topic as string | null) ?? null,
    assignmentId: (row.assignment_id as string | null) ?? null,
    studyMode: (row.study_mode as StudyContext["studyMode"]) ?? "balanced",
    startingPoint: (row.starting_point as string | null) ?? null,
    conceptsCovered: Array.isArray(row.concepts_covered)
      ? (row.concepts_covered as string[])
      : [],
    topicsToRevisit: Array.isArray(row.topics_to_revisit)
      ? (row.topics_to_revisit as string[])
      : [],
    studyNote: (row.study_note as string | null) ?? null,
    updatedAt: (row.updated_at as string | null) ?? null,
  };
}

function mapResolvedCourse(row: Record<string, unknown> | null): ResolvedCourse | null {
  if (!row?.course_id) return null;
  return {
    courseId: row.course_id as string,
    courseName: (row.course_name as string | null) ?? null,
    courseCode: (row.course_code as string | null) ?? null,
  };
}

export function mapCourseRoutingResult(row: Record<string, unknown>): CourseRoutingResult {
  const candidates = Array.isArray(row.candidates)
    ? (row.candidates as Record<string, unknown>[])
        .map((c) => mapResolvedCourse(c))
        .filter((c): c is ResolvedCourse => c != null)
    : [];
  return {
    outcome: (row.outcome as CourseRoutingResult["outcome"]) ?? "unresolved",
    course: mapResolvedCourse((row.course as Record<string, unknown>) ?? null),
    evidence: Array.isArray(row.evidence) ? (row.evidence as string[]) : [],
    candidates,
    reason: typeof row.reason === "string" ? row.reason : "Unknown",
  };
}

export function mapAcademicContext(row: Record<string, unknown>): AcademicContext {
  if (!row.course_id || typeof row.course_id !== "string") {
    throw new AcademicApiMalformedError("Academic context missing course_id");
  }
  return {
    courseId: row.course_id,
    courseName: (row.course_name as string | null) ?? null,
    courseCode: (row.course_code as string | null) ?? null,
    routingEvidence: Array.isArray(row.routing_evidence)
      ? (row.routing_evidence as string[])
      : [],
    profilePreferences: mapPreferences(row.profile_preferences as BackendPreferences),
    courseInstructions: (row.course_instructions as string | null) ?? null,
    studyContext: mapStudyContext(row.study_context as Record<string, unknown>),
  };
}

/** Map frontend course profile update to backend PUT body. */
export function mapCourseProfileUpdateToBackend(
  prefs: Partial<CourseProfileData>,
): Record<string, unknown> {
  return {
    display_alias: prefs.displayAlias ?? null,
    short_label: prefs.shortLabel ?? null,
    description: prefs.description ?? null,
    teaching_depth: prefs.teachingDepth,
    starting_level: prefs.startingLevel,
    explanation_style: prefs.explanationStyle,
    answer_style: prefs.answerStyle,
    step_by_step: prefs.stepByStep ?? null,
    exam_style: prefs.examStyle,
    visual_preference: prefs.visualPreference,
    math_detail: prefs.mathDetail,
    code_detail: prefs.codeDetail,
    terminology_notes: prefs.terminologyNotes ?? null,
    study_instructions: prefs.studyInstructions ?? null,
    enabled: prefs.enabled ?? true,
  };
}

export function mapStudyContextUpdateToBackend(
  ctx: Partial<StudyContext>,
): Record<string, unknown> {
  return {
    current_topic: ctx.currentTopic ?? null,
    assignment_id: ctx.assignmentId ?? null,
    study_mode: ctx.studyMode,
    starting_point: ctx.startingPoint ?? null,
    concepts_covered: ctx.conceptsCovered ?? [],
    topics_to_revisit: ctx.topicsToRevisit ?? [],
    study_note: ctx.studyNote ?? null,
  };
}

export function mapCourseRoutingRequestToBackend(
  request: import("@/lib/domain/course-intelligence").CourseRoutingRequest,
): Record<string, unknown> {
  return {
    course_id: request.courseId ?? null,
    assignment_id: request.assignmentId ?? null,
    document_id: request.documentId ?? null,
    module_id: request.moduleId ?? null,
    module_item_id: request.moduleItemId ?? null,
    active_course_id: request.activeCourseId ?? null,
    text: request.text ?? null,
  };
}
