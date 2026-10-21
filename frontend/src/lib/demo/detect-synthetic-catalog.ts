import type { Course } from "@/lib/domain/types";
import type { AssistantRuntimeStatus } from "@/lib/api/http/assistant-status";

export function isSyntheticCourseId(courseId: string | null | undefined): boolean {
  if (!courseId) return false;
  return courseId.startsWith("synthetic-");
}

export function isSyntheticCatalog(courses: Course[]): boolean {
  if (!courses.length) return false;
  return courses.every((c) => isSyntheticCourseId(c.id));
}

export function hasRealSyncedCourses(courses: Course[]): boolean {
  return courses.some((c) => !isSyntheticCourseId(c.id));
}

export function shouldShowDemoDataBadge(
  mode: "mock" | "http",
  courses: Course[],
  assistantStatus: AssistantRuntimeStatus | null,
): boolean {
  if (mode === "mock") return true;
  if (hasRealSyncedCourses(courses)) return false;
  if (assistantStatus?.provider === "synthetic" && isSyntheticCatalog(courses)) return true;
  return isSyntheticCatalog(courses);
}
