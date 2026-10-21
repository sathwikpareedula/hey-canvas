import Link from "next/link";
import { CourseBadge } from "@/components/course/CourseBadge";
import type { Assignment, Course } from "@/lib/domain/types";
import { deadlineWindowLabel, formatDueDate } from "@/lib/utils/date";

export function AssignmentRow({
  assignment,
  course,
  compact,
  href,
}: {
  assignment: Assignment;
  course?: Course;
  compact?: boolean;
  href?: string;
}) {
  const status = deadlineWindowLabel(assignment.deadlineWindow);
  const inner = (
    <>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-medium break-words text-[var(--foreground)]">{assignment.title}</h3>
        {status ? (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
              assignment.deadlineWindow === "past_due_time"
                ? "bg-[var(--warn-bg)] text-[var(--warn-text)]"
                : "bg-[var(--surface-muted)] text-[var(--muted)]"
            }`}
          >
            {status}
          </span>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
        {course ? <CourseBadge course={course} /> : null}
        <time dateTime={assignment.dueAt ?? undefined}>{formatDueDate(assignment.dueAt)}</time>
        {assignment.pointsPossible != null ? (
          <span>{assignment.pointsPossible} pts</span>
        ) : null}
      </div>
    </>
  );

  const className = `flex flex-col gap-1 border-b border-[var(--border)] last:border-b-0 ${
    compact ? "py-2" : "py-3"
  }`;

  if (href) {
    return (
      <Link href={href} className={`${className} block hover:bg-[var(--surface-muted)]/40`}>
        {inner}
      </Link>
    );
  }

  return <article className={className}>{inner}</article>;
}
