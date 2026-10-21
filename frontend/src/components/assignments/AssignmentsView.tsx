"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AssignmentRow } from "@/components/assignment/AssignmentRow";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { Assignment, Course, DeadlineWindow } from "@/lib/domain/types";

const WINDOWS: { value: DeadlineWindow | ""; label: string }[] = [
  { value: "", label: "All windows" },
  { value: "today", label: "Today" },
  { value: "tomorrow", label: "Tomorrow" },
  { value: "this_week", label: "This week" },
  { value: "next_7_days", label: "Next 7 days" },
  { value: "upcoming", label: "Upcoming" },
  { value: "past_due_time", label: "Past due time" },
];

export function AssignmentsView() {
  const api = useAcademicApi();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [courseId, setCourseId] = useState(searchParams.get("course") ?? "");
  const [window, setWindow] = useState<DeadlineWindow | "">(
    (searchParams.get("window") as DeadlineWindow) ?? "",
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const coursesById = useMemo(() => new Map(courses.map((c) => [c.id, c])), [courses]);

  const syncUrl = useCallback(
    (next: { course?: string; window?: string }) => {
      const params = new URLSearchParams();
      const c = next.course ?? courseId;
      const w = next.window ?? window;
      if (c) params.set("course", c);
      if (w) params.set("window", w);
      const qs = params.toString();
      router.replace(qs ? `/assignments?${qs}` : "/assignments");
    },
    [router, courseId, window],
  );

  useEffect(() => {
    api.getCourses().then(setCourses).catch((err) => setError(err));
  }, [api]);

  useEffect(() => {
    let active = true;
    api
      .getAssignments({
        courseId: courseId || undefined,
        window: window || undefined,
      })
      .then((data) => {
        if (active) setAssignments(data);
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
  }, [api, courseId, window, reloadKey]);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap gap-3">
        <label className="text-sm">
          <span className="text-[var(--muted)]">Course</span>
          <select
            value={courseId}
            onChange={(e) => {
              setLoading(true);
              setCourseId(e.target.value);
              syncUrl({ course: e.target.value });
            }}
            className="ml-2 rounded-md border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1 text-sm"
          >
            <option value="">All courses</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-[var(--muted)]">Time window</span>
          <select
            value={window}
            onChange={(e) => {
              setLoading(true);
              setWindow(e.target.value as DeadlineWindow | "");
              syncUrl({ window: e.target.value });
            }}
            className="ml-2 rounded-md border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1 text-sm"
          >
            {WINDOWS.map((w) => (
              <option key={w.label} value={w.value}>{w.label}</option>
            ))}
          </select>
        </label>
      </div>
      {error ? (
        <ApiErrorPanel
          error={error}
          onRetry={() => {
            setError(null);
            setLoading(true);
            setReloadKey((k) => k + 1);
          }}
        />
      ) : null}
      {loading ? (
        <PageSkeleton />
      ) : !error && assignments.length === 0 ? (
        <EmptyState
          title="No assignments in this view"
          description="Nothing matches your filters, or no assignments are indexed yet."
        />
      ) : !error ? (
        <div className="rounded-xl border border-[var(--border)] px-3">
          {assignments.map((a) => (
            <AssignmentRow
              key={a.id}
              assignment={a}
              course={coursesById.get(a.courseId)}
              href={`/assignments/${a.id}`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
