import type {
  BackendStudyMode,
  EvidenceReference,
  PracticeFeedback,
  PracticeQuestion,
  PracticeSession,
  StudyGuide,
  StudyGuideRequest,
  StudySession,
  StudySessionCreateRequest,
} from "@/lib/domain/study-workflows";
import { mapUiStudyModeToAssistantBackend } from "@/lib/api/http/assistant-adapters";
import type { StudyMode } from "@/lib/domain/study-mode";
import {
  normalizeStudySessionPayload,
} from "@/lib/study/present-study-session";
import { finiteNumber, finitePercent } from "@/lib/utils/numbers";

type JsonRecord = Record<string, unknown>;

function pickString(row: JsonRecord, keys: string[], fallback: string): string {
  for (const key of keys) {
    const v = row[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return fallback;
}

export function mapUiStudyModeToBackend(mode: StudyMode): BackendStudyMode {
  const mapped = mapUiStudyModeToAssistantBackend(mode);
  return mapped as BackendStudyMode;
}

export function mapEvidenceReference(row: JsonRecord): EvidenceReference {
  return {
    authority: String(row.authority ?? "professor_material"),
    identifier: String(row.identifier ?? ""),
    locator: typeof row.locator === "string" ? row.locator : null,
  };
}

export function mapStudySessionCreateToBackend(req: StudySessionCreateRequest) {
  return {
    course_id: req.courseId,
    goal: req.goal,
    duration_minutes: req.durationMinutes,
    topics: req.topics,
    study_mode: req.studyMode,
    assignment_ids: req.assignmentIds,
  };
}

export function mapBackendStudySession(raw: JsonRecord): StudySession {
  const row = normalizeStudySessionPayload(raw);
  const steps = Array.isArray(row.steps)
    ? row.steps.map((s) => {
        const step = s as JsonRecord;
        return {
          order: finiteNumber(step.order, 1),
          title: pickString(step, ["title", "name", "label"], "Step"),
          minutes: finiteNumber(step.minutes ?? step.duration_minutes, 15),
          status: pickString(step, ["status"], "pending"),
        };
      })
    : [];
  const assignmentIds = Array.isArray(row.assignment_ids)
    ? row.assignment_ids.map(String)
    : Array.isArray(row.assignmentIds)
      ? row.assignmentIds.map(String)
      : [];
  return {
    sessionId: pickString(row, ["session_id", "sessionId", "id"], ""),
    courseId: pickString(row, ["course_id", "courseId"], ""),
    goal: pickString(row, ["goal", "title", "name"], "Study plan"),
    durationMinutes: finiteNumber(row.duration_minutes ?? row.durationMinutes, 45),
    topics: Array.isArray(row.topics) ? row.topics.map(String) : [],
    studyMode: pickString(row, ["study_mode", "studyMode"], "learn") as BackendStudyMode,
    assignmentIds,
    status: pickString(row, ["status"], "active") as StudySession["status"],
    relevantEvidence: Array.isArray(row.relevant_evidence)
      ? row.relevant_evidence.map((e) => mapEvidenceReference(e as JsonRecord))
      : Array.isArray(row.relevantEvidence)
        ? row.relevantEvidence.map((e) => mapEvidenceReference(e as JsonRecord))
        : [],
    steps,
    progress: finitePercent(row.progress, 0),
  };
}

export function mapPracticeCreateToBackend(courseId: string, topic: string, totalQuestions: number) {
  return {
    course_id: courseId,
    topic,
    total_questions: totalQuestions,
    study_mode: "practice",
  };
}

function mapPracticeQuestion(row: JsonRecord | null | undefined): PracticeQuestion | null {
  if (!row) return null;
  return {
    question: String(row.question ?? ""),
    generated: Boolean(row.generated ?? true),
    evidence: Array.isArray(row.evidence)
      ? row.evidence.map((e) => mapEvidenceReference(e as JsonRecord))
      : [],
  };
}

export function mapBackendPracticeSession(row: JsonRecord): PracticeSession {
  const r =
    row.practice_session && typeof row.practice_session === "object"
      ? (row.practice_session as JsonRecord)
      : row;
  const total = finiteNumber(r.total_questions ?? r.totalQuestions, 1);
  const index = finiteNumber(r.question_index ?? r.questionIndex, 0);
  return {
    sessionId: pickString(r, ["session_id", "sessionId"], ""),
    courseId: pickString(r, ["course_id", "courseId"], ""),
    topic: pickString(r, ["topic"], "Practice"),
    status: pickString(r, ["status"], "active"),
    questionIndex: index,
    totalQuestions: Math.max(total, index + 1),
    correctAnswers: finiteNumber(r.correct_answers ?? r.correctAnswers, 0),
    question: mapPracticeQuestion(r.question as JsonRecord | null),
    progress: finitePercent(r.progress, 0),
  };
}

export function mapBackendPracticeFeedback(row: JsonRecord): PracticeFeedback {
  return {
    correct: Boolean(row.correct),
    feedback: String(row.feedback ?? ""),
    hint: typeof row.hint === "string" ? row.hint : null,
    nextQuestion: mapPracticeQuestion(row.next_question as JsonRecord | null),
    progress: Number(row.progress ?? 0),
  };
}

export function mapStudyGuideRequestToBackend(req: StudyGuideRequest) {
  return {
    course_id: req.courseId,
    topic: req.topic,
    assignment_id: req.assignmentId,
    document_id: req.documentId,
    study_mode: req.studyMode ?? "review",
  };
}

export function mapBackendStudyGuide(row: JsonRecord): StudyGuide {
  const list = (key: string) =>
    Array.isArray(row[key]) ? (row[key] as unknown[]).map(String) : [];
  return {
    title: String(row.title ?? "Study guide"),
    scope: String(row.scope ?? ""),
    keyConcepts: list("key_concepts"),
    explanations: list("explanations"),
    evidence: Array.isArray(row.evidence)
      ? row.evidence.map((e) => mapEvidenceReference(e as JsonRecord))
      : [],
    reviewChecklist: list("review_checklist"),
    practicePrompts: list("practice_prompts"),
    uncertainties: list("uncertainties"),
  };
}
