import type { StudySession } from "@/lib/domain/study-workflows";
import { finiteNumber, finitePercent } from "@/lib/utils/numbers";

type JsonRecord = Record<string, unknown>;

/** Normalize backend StudySessionView / camelCase variants before mapping. */
export function normalizeStudySessionPayload(raw: JsonRecord): JsonRecord {
  let row: JsonRecord = raw;
  for (const key of ["study_session", "session", "view"]) {
    const nested = row[key];
    if (nested && typeof nested === "object") {
      row = { ...row, ...(nested as JsonRecord) };
    }
  }
  return row;
}

export function studySessionGoalLabel(session: Pick<StudySession, "goal" | "topics">): string {
  const goal = session.goal?.trim();
  if (goal && goal !== "undefined") return goal;
  const topic = session.topics?.find((t) => t.trim());
  if (topic) return `Study: ${topic}`;
  return "Study plan";
}

export function studySessionDurationLabel(minutes: number): string {
  const m = finiteNumber(minutes, 0);
  if (m <= 0) return "Duration flexible";
  return `${m} min`;
}

export function studySessionProgressLabel(progress: number): string {
  return `${finitePercent(progress, 0)}% complete`;
}
