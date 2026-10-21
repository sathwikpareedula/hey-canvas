import type { StudyMode } from "@/lib/domain/study-mode";

export function buildStudyWorkspaceUrl(options?: {
  courseId?: string;
  studyMode?: StudyMode;
  assignmentId?: string;
  documentId?: string;
  continueSession?: boolean;
  practiceTopic?: string;
}): string {
  const params = new URLSearchParams();
  if (options?.courseId) params.set("courseId", options.courseId);
  if (options?.studyMode) params.set("studyMode", options.studyMode);
  if (options?.assignmentId) params.set("assignmentId", options.assignmentId);
  if (options?.documentId) params.set("documentId", options.documentId);
  if (options?.continueSession) params.set("continue", "1");
  if (options?.practiceTopic) params.set("practiceTopic", options.practiceTopic);
  const qs = params.toString();
  return qs ? `/study?${qs}` : "/study";
}

export function pickDefaultStudyCourseId(
  courses: { id: string }[],
  dueToday: { courseId: string }[],
  thisWeek: { courseId: string }[],
): string | undefined {
  return dueToday[0]?.courseId ?? thisWeek[0]?.courseId ?? courses[0]?.id;
}

export function buildStudyGuideUrl(options?: {
  courseId?: string;
  topic?: string;
  assignmentId?: string;
  documentId?: string;
}): string {
  const params = new URLSearchParams();
  if (options?.courseId) params.set("courseId", options.courseId);
  if (options?.topic) params.set("topic", options.topic);
  if (options?.assignmentId) params.set("assignmentId", options.assignmentId);
  if (options?.documentId) params.set("documentId", options.documentId);
  const qs = params.toString();
  return qs ? `/study/guide?${qs}` : "/study/guide";
}
