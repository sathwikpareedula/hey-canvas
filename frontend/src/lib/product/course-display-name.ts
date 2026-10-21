import type { Course } from "@/lib/domain/types";
import type { CourseProfile } from "@/lib/domain/course-intelligence";
import { formatCourseLabel } from "@/lib/courses/display";

export function courseDisplayName(
  course: Course,
  profile?: CourseProfile | null,
): string {
  const alias = profile?.profile?.displayAlias?.trim();
  if (alias) return alias;
  const short = profile?.profile?.shortLabel?.trim();
  if (short) return short;
  return formatCourseLabel(course);
}

export function courseNavLabel(course: Course, profile?: CourseProfile | null): string {
  const name = courseDisplayName(course, profile);
  if (name.length <= 42) return name;
  return `${name.slice(0, 39)}…`;
}
