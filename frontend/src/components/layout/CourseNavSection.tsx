"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { useFocusCourses } from "@/contexts/FocusCoursesContext";
import { courseNavLabel } from "@/lib/product/course-display-name";

function useIsClient(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function CourseNavSection() {
  const pathname = usePathname();
  const { focusCourses, loading } = useFocusCourses();
  const isClient = useIsClient();

  if (!isClient) {
    return (
      <p className="px-3 py-1 text-xs text-[var(--muted)]" role="status" suppressHydrationWarning>
        Loading courses…
      </p>
    );
  }

  if (loading && focusCourses.length === 0) {
    return (
      <p className="px-3 py-1 text-xs text-[var(--muted)]" role="status">
        Loading courses…
      </p>
    );
  }

  if (focusCourses.length === 0) {
    return (
      <div className="px-3 py-1">
        <p className="text-xs text-[var(--muted)]">No focus courses yet.</p>
        <Link href="/settings#focus-courses" className="text-xs text-[var(--accent)] underline">
          Choose focus courses
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      <p className="px-3 pt-2 text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--muted)]">
        My courses
      </p>
      {focusCourses.map((course) => {
        const href = `/courses/${course.id}`;
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={course.id}
            href={href}
            title={course.name}
            className={`block truncate rounded-lg px-3 py-2 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
              active
                ? "bg-[var(--surface-muted)] font-medium text-[var(--foreground)]"
                : "text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]"
            }`}
            aria-current={active ? "page" : undefined}
          >
            {courseNavLabel(course)}
          </Link>
        );
      })}
    </div>
  );
}
