/** Frontend contracts aligned with Course Profiles backend (provider-neutral). */

export type TeachingDepth = "concise" | "balanced" | "detailed";
export type StartingLevel =
  | "zero_knowledge"
  | "course_context"
  | "intermediate"
  | "advanced";
export type ExplanationStyle =
  | "concept_first"
  | "step_by_step"
  | "worked_examples"
  | "diagram_aware";
export type AnswerStyle = "balanced" | "concise" | "exam_style";
export type DetailPreference = "auto" | "light" | "detailed";

export interface CourseStudyPreferences {
  teachingDepth: TeachingDepth;
  startingLevel: StartingLevel;
  explanationStyle: ExplanationStyle;
  answerStyle: AnswerStyle;
  stepByStep: boolean | null;
  examStyle: boolean;
  visualPreference: DetailPreference;
  mathDetail: DetailPreference;
  codeDetail: DetailPreference;
}

export interface CourseProfileData extends CourseStudyPreferences {
  displayAlias: string | null;
  shortLabel: string | null;
  description: string | null;
  terminologyNotes: string | null;
  studyInstructions: string | null;
  enabled: boolean;
}

export interface CourseProfile {
  courseId: string;
  courseName: string | null;
  courseCode: string | null;
  hasCustomProfile: boolean;
  profile: CourseProfileData | null;
  effectivePreferences: CourseStudyPreferences;
  effectiveCourseInstructions: string | null;
  updatedAt: string | null;
}

export type BackendStudyContextMode = "balanced" | "review" | "practice" | "exam_prep";

export interface StudyContext {
  courseId: string;
  courseName: string | null;
  hasContext: boolean;
  currentTopic: string | null;
  assignmentId: string | null;
  studyMode: BackendStudyContextMode;
  startingPoint: string | null;
  conceptsCovered: string[];
  topicsToRevisit: string[];
  studyNote: string | null;
  updatedAt: string | null;
}

export type CourseRoutingOutcome = "resolved" | "ambiguous" | "unresolved";

export interface CourseRoutingRequest {
  courseId?: string;
  assignmentId?: string;
  documentId?: string;
  moduleId?: string;
  moduleItemId?: string;
  activeCourseId?: string;
  text?: string;
}

export interface ResolvedCourse {
  courseId: string;
  courseName: string | null;
  courseCode: string | null;
}

export interface CourseRoutingResult {
  outcome: CourseRoutingOutcome;
  course: ResolvedCourse | null;
  evidence: string[];
  candidates: ResolvedCourse[];
  reason: string;
}

export interface AcademicContext {
  courseId: string;
  courseName: string | null;
  courseCode: string | null;
  routingEvidence: string[];
  profilePreferences: CourseStudyPreferences;
  courseInstructions: string | null;
  studyContext: StudyContext;
}

export const TEACHING_DEPTH_LABELS: Record<TeachingDepth, string> = {
  concise: "Concise",
  balanced: "Balanced",
  detailed: "Detailed",
};

export const STARTING_LEVEL_LABELS: Record<StartingLevel, string> = {
  zero_knowledge: "From scratch",
  course_context: "With course context",
  intermediate: "Intermediate",
  advanced: "Advanced",
};
