"use client";

import type { Course } from "@/lib/domain/types";
import {
  bucketCoursesForFocus,
  toggleFocusCourseId,
} from "@/lib/product/focus-courses";
import { courseNavLabel } from "@/lib/product/course-display-name";

export function FocusCoursePicker({
  catalog,
  selectedIds,
  onChange,
}: {
  catalog: Course[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const buckets = bucketCoursesForFocus(catalog);

  const renderGroup = (title: string, courses: Course[], hint?: string) => {
    if (!courses.length) return null;
    return (
      <section className="space-y-2">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          {hint ? <p className="text-xs text-[var(--muted)]">{hint}</p> : null}
        </div>
        <ul className="space-y-1">
          {courses.map((course) => {
            const checked = selectedIds.includes(course.id);
            return (
              <li key={course.id}>
                <label
                  className="flex cursor-pointer items-start gap-2 rounded-lg border border-[var(--border)] px-3 py-2 hover:bg-[var(--surface-muted)]"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={checked}
                    onChange={() => onChange(toggleFocusCourseId(course.id, selectedIds))}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium" title={course.name}>
                      {courseNavLabel(course)}
                    </span>
                    {course.term ? (
                      <span className="text-xs text-[var(--muted)]">{course.term}</span>
                    ) : null}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </section>
    );
  };

  if (!catalog.length) {
    return (
      <p className="text-sm text-[var(--muted)]">
        No courses in your local index yet. Connect Canvas and run a sync on your computer, then
        return here.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {renderGroup(
        "Likely this term",
        buckets.likelyCurrent,
        "Suggested focus courses based on your synced catalog.",
      )}
      {renderGroup("Other current courses", buckets.otherCurrent)}
      {renderGroup("Past courses", buckets.past, "You can still add these if you need them.")}
      {renderGroup("Training / resources", buckets.trainingOrResources)}
    </div>
  );
}
