"use client";

import type { Course } from "@/lib/domain/types";
import { courseNavLabel } from "@/lib/product/course-display-name";

export function ContextModeBadge({
  course,
  scoped,
}: {
  course: Course | null;
  scoped: boolean;
}) {
  if (scoped && course) {
    return (
      <span
        className="inline-flex max-w-full items-center gap-1 rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs text-[var(--foreground)]"
        title={course.name}
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" aria-hidden />
        <span className="truncate">{courseNavLabel(course)}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs text-[var(--muted)]">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--muted)]" aria-hidden />
      All courses
    </span>
  );
}
