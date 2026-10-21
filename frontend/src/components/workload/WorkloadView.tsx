"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { Assignment, Course } from "@/lib/domain/types";

function dayKey(d: Date): string {
  return d.toLocaleDateString(undefined, { year: "numeric", month: "2-digit", day: "2-digit" });
}

export function WorkloadView() {
  const api = useAcademicApi();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getAssignments(), api.getCourses()])
      .then(([a, c]) => {
        if (!active) return;
        setAssignments(a.filter((x) => x.dueAt));
        setCourses(c);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const coursesById = useMemo(() => new Map(courses.map((c) => [c.id, c])), [courses]);

  const days = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const buckets: {
      weekday: string;
      dateText: string;
      label: string;
      key: string;
      items: Assignment[];
    }[] = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      const weekday = d.toLocaleDateString(undefined, { weekday: "short" });
      const dateText = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      buckets.push({
        key: dayKey(d),
        weekday,
        dateText,
        label: `${weekday}, ${dateText}`,
        items: [],
      });
    }
    for (const a of assignments) {
      if (!a.dueAt) continue;
      const due = new Date(a.dueAt);
      const key = dayKey(due);
      const bucket = buckets.find((b) => b.key === key);
      if (bucket) bucket.items.push(a);
    }
    return buckets;
  }, [assignments]);

  const busiest = days.reduce((max, d) => (d.items.length > max.items.length ? d : max), days[0]);

  if (loading) return <PageSkeleton />;
  if (error) return <ApiErrorPanel error={error} />;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h2 className="text-xl font-semibold">Next 7 days</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Indexed assignment deadlines grouped by your local date. Busiest day:{" "}
          <span className="font-medium text-[var(--foreground)]">
            {busiest?.label} ({busiest?.items.length} items)
          </span>
        </p>
      </header>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {days.map((day) => (
          <div
            key={day.key}
            className={`min-w-0 overflow-hidden rounded-xl border p-3 ${
              day.items.length >= 2
                ? "border-[var(--accent)] bg-[var(--surface)] shadow-xs"
                : "border-[var(--border)] bg-[var(--surface)]"
            }`}
          >
            <div className="border-b border-[var(--border)] pb-2">
              <p className="text-xs font-semibold text-[var(--foreground)]">{day.weekday}</p>
              <p className="text-[11px] text-[var(--muted)]">{day.dateText}</p>
            </div>
            <p className="mt-2 text-2xl font-semibold tracking-tight">{day.items.length}</p>
            <p className="text-[10px] text-[var(--muted)]">
              {day.items.length === 1 ? "deadline" : "deadlines"}
            </p>
            <ul className="mt-3 space-y-2 border-t border-[var(--border)]/60 pt-2">
              {day.items.slice(0, 3).map((a) => (
                <li key={a.id} className="min-w-0">
                  <Link
                    href={`/assignments/${a.id}`}
                    className="line-clamp-2 block text-xs font-medium hover:text-[var(--accent)] hover:underline break-words"
                    title={a.title}
                  >
                    {a.title}
                  </Link>
                  <span
                    className="mt-0.5 block truncate text-[10px] text-[var(--muted)]"
                    title={coursesById.get(a.courseId)?.name}
                  >
                    {coursesById.get(a.courseId)?.name}
                  </span>
                </li>
              ))}
              {day.items.length > 3 ? (
                <li className="pt-1 text-[10px] font-medium text-[var(--muted)]">
                  +{day.items.length - 3} more
                </li>
              ) : null}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
