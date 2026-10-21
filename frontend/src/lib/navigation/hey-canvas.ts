import type { StudyMode } from "@/lib/domain/study-mode";

export function buildHeyCanvasUrl(options?: {
  courseId?: string;
  prompt?: string;
  assignmentId?: string;
  documentId?: string;
  studyMode?: StudyMode;
}): string {
  const params = new URLSearchParams();
  if (options?.courseId) params.set("courseId", options.courseId);
  if (options?.prompt) params.set("prompt", options.prompt);
  if (options?.assignmentId) params.set("assignmentId", options.assignmentId);
  if (options?.documentId) params.set("documentId", options.documentId);
  if (options?.studyMode) params.set("studyMode", options.studyMode);
  const qs = params.toString();
  return qs ? `/?${qs}` : "/";
}
