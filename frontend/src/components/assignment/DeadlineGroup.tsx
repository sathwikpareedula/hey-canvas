import { AssignmentRow } from "@/components/assignment/AssignmentRow";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Assignment, Course } from "@/lib/domain/types";

const EMPTY_COPY: Record<string, string> = {
  "Due today": "Nothing due today.",
  "Due tomorrow": "Nothing due tomorrow.",
  "This week": "Nothing due this week.",
  Overdue: "No overdue assignments.",
};

export function DeadlineGroup({
  title,
  assignments,
  coursesById,
  compact,
  emptyDescription,
}: {
  title: string;
  assignments: Assignment[];
  coursesById: Map<string, Course>;
  compact?: boolean;
  emptyDescription?: string;
}) {
  return (
    <section aria-labelledby={`deadline-${title}`} className="space-y-2">
      <h2 id={`deadline-${title}`} className="text-sm font-semibold tracking-tight text-[var(--foreground)]">
        {title}
      </h2>
      {assignments.length === 0 ? (
        <EmptyState
          title="Nothing scheduled"
          description={emptyDescription ?? EMPTY_COPY[title] ?? "No items in this window."}
        />
      ) : (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4">
          {assignments.map((a) => (
            <AssignmentRow
              key={a.id}
              assignment={a}
              course={coursesById.get(a.courseId)}
              compact={compact}
              href={`/assignments/${a.id}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}
