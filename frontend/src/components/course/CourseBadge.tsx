import { coursePrimaryTitle, courseSecondaryLabel } from "@/lib/courses/display";
import type { Course } from "@/lib/domain/types";

export function CourseBadge({ course }: { course: Pick<Course, "name" | "color" | "code"> }) {
  const primary = coursePrimaryTitle(course);
  const secondary = courseSecondaryLabel(course);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)]">
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: course.color ?? "var(--accent)" }}
        aria-hidden
      />
      <span className="truncate">
        {primary}
        {secondary ? ` · ${secondary}` : ""}
      </span>
    </span>
  );
}
