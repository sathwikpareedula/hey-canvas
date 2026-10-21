"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { CourseBadge } from "@/components/course/CourseBadge";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { Course } from "@/lib/domain/types";

export function CoursesView() {
  const api = useAcademicApi();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [query, setQuery] = useState("");
  const [term, setTerm] = useState("");

  const terms = useMemo(
    () =>
      Array.from(
        new Set(courses.map((c) => c.term).filter((t): t is string => Boolean(t))),
      ).sort(),
    [courses],
  );

  const visibleCourses = useMemo(
    () =>
      courses.filter((c) => {
        const matchesQuery = `${c.name} ${c.code ?? ""}`
          .toLocaleLowerCase()
          .includes(query.trim().toLocaleLowerCase());
        return matchesQuery && (!term || c.term === term);
      }),
    [courses, query, term],
  );

  useEffect(() => {
    let active = true;
    api
      .getCourses()
      .then((items) => {
        if (active) {
          setCourses(items);
          setError(null);
        }
      })
      .catch((err) => {
        if (active) setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, reloadKey]);

  if (loading) return <LoadingState />;
  if (error) {
    return (
      <ApiErrorPanel
        error={error}
        onRetry={() => {
          setLoading(true);
          setReloadKey((k) => k + 1);
        }}
      />
    );
  }

  if (courses.length === 0) {
    return (
      <EmptyState
        title="No courses available"
        description="Sync courses through the local backend CLI. This is not a UI crash — there is simply no data yet."
      />
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <label className="min-w-48 flex-1 text-sm font-medium">
          Search courses
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Course name or code"
            className="mt-2 block w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm font-medium">
          Term
          <select
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            className="mt-2 block w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
          >
            <option value="">All terms</option>
            {terms.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-sm text-[var(--muted)]" aria-live="polite">
        {visibleCourses.length} of {courses.length} courses
      </p>
      {visibleCourses.length === 0 ? (
        <EmptyState title="No matching courses" description="Try a different course name or term." />
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {visibleCourses.map((course) => (
          <div
            key={course.id}
            className="flex flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
          >
            <Link
              href={`/courses/${course.id}`}
              className="flex-1 transition hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            >
              <CourseBadge course={course} />
              <p className="mt-3 text-base font-medium">{course.name}</p>
              {course.term ? <p className="text-xs text-[var(--muted)]">{course.term}</p> : null}
              <p className="mt-3 text-xs text-[var(--accent)]">Open workspace →</p>
            </Link>
            <Link
              href={buildHeyCanvasUrl({
                courseId: course.id,
                prompt: `Help me study for ${course.name}.`,
              })}
              className="mt-3 text-xs text-[var(--muted)] underline"
            >
              Study with Hey Canvas
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
