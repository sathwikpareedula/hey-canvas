import type { Course } from "@/lib/domain/types";

const CANVAS_SIS_PREFIX = /^\d{4}-[A-Z]{2,4}-\d{4}-\d{3}-/i;

/** Prefer human title over Canvas SIS-style name when they differ. */
export function coursePrimaryTitle(course: Pick<Course, "name" | "code">): string {
  const name = course.name?.trim() ?? "";
  const code = course.code?.trim() ?? "";
  if (!name) return code || "Course";
  if (CANVAS_SIS_PREFIX.test(name) && code && !CANVAS_SIS_PREFIX.test(code)) {
    const tail = name.replace(CANVAS_SIS_PREFIX, "").replace(/[-_]+/g, " ").trim();
    if (tail.length > 3) return titleCaseWords(tail);
  }
  if (name.length > 60 && code && code.length < name.length) {
    return code;
  }
  return name;
}

export function courseSecondaryLabel(course: Pick<Course, "name" | "code">): string | null {
  const primary = coursePrimaryTitle(course);
  const code = course.code?.trim();
  if (!code || code === primary) return null;
  if (primary === course.name?.trim() && code) return code;
  return code;
}

function titleCaseWords(text: string): string {
  return text
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCourseLabel(course: Pick<Course, "name" | "code">): string {
  const primary = coursePrimaryTitle(course);
  const secondary = courseSecondaryLabel(course);
  return secondary ? `${primary} (${secondary})` : primary;
}
