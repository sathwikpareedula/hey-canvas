"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { AssignmentRow } from "@/components/assignment/AssignmentRow";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import type { Assignment, Course } from "@/lib/domain/types";

function dayKey(date: Date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}

export function CalendarView() {
  const api = useAcademicApi();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selected, setSelected] = useState(() => dayKey(new Date()));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([api.getAssignments({}), api.getCourses()])
      .then(([a, c]) => { if (active) { setAssignments(a); setCourses(c); setError(null); setLoading(false); } })
      .catch((e) => { if (active) { setError(e); setLoading(false); } });
    return () => { active = false; };
  }, [api, reload]);

  const byDay = useMemo(() => {
    const grouped = new Map<string, Assignment[]>();
    for (const assignment of assignments) {
      if (!assignment.dueAt) continue;
      const due = new Date(assignment.dueAt);
      if (Number.isNaN(due.getTime())) continue;
      const key = dayKey(due);
      grouped.set(key, [...(grouped.get(key) ?? []), assignment]);
    }
    return grouped;
  }, [assignments]);
  const coursesById = useMemo(() => new Map(courses.map((c) => [c.id, c])), [courses]);
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = first.getDay();
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells = Array.from({ length: Math.ceil((offset + days) / 7) * 7 }, (_, i) => i - offset + 1);
  const chosen = byDay.get(selected) ?? [];
  const monthName = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(month);
  const move = (delta: number) => {
    const next = new Date(month.getFullYear(), month.getMonth() + delta, 1);
    setMonth(next);
    setSelected(dayKey(next));
  };

  if (loading) return <PageSkeleton />;
  if (error) return <ApiErrorPanel error={error} onRetry={() => { setError(null); setLoading(true); setReload((n) => n + 1); }} />;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-2xl font-semibold">Academic calendar</h2><p className="mt-1 text-sm text-[var(--muted)]">Assignment deadlines from your current academic index. Not a class-meeting calendar.</p></div>
        <Link href="/assignments" className="rounded-xl border border-[var(--border)] px-4 py-2 text-sm">All assignments ↗</Link>
      </header>
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]" aria-label="Deadline calendar">
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] p-4">
          <button type="button" onClick={() => move(-1)} aria-label="Previous month" className="rounded-lg border border-[var(--border)] px-3 py-2">←</button>
          <h3 className="font-semibold" aria-live="polite">{monthName}</h3>
          <button type="button" onClick={() => move(1)} aria-label="Next month" className="rounded-lg border border-[var(--border)] px-3 py-2">→</button>
        </div>
        <div className="grid grid-cols-7 text-center text-xs font-semibold text-[var(--muted)]">
          {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((day) => <div key={day} className="py-3">{day}</div>)}
        </div>
        <div className="grid grid-cols-7 border-t border-[var(--border)]">
          {cells.map((date, i) => {
            if (date < 1 || date > days) return <div key={i} aria-hidden="true" className="min-h-16 border-b border-r border-[var(--border)] bg-[var(--surface-muted)]/30 sm:min-h-24" />;
            const key = dayKey(new Date(month.getFullYear(), month.getMonth(), date));
            const count = byDay.get(key)?.length ?? 0;
            return <button type="button" key={key} onClick={() => setSelected(key)} aria-pressed={selected === key}
              aria-label={`${key}: ${count} assignment deadline${count === 1 ? "" : "s"}`}
              className={`flex min-h-16 flex-col items-center gap-2 border-b border-r border-[var(--border)] p-2 text-sm hover:bg-[var(--surface-muted)] sm:min-h-24 ${selected === key ? "bg-[var(--surface-muted)] font-semibold text-[var(--accent)]" : ""}`}>
              <span>{date}</span>{count > 0 && <span className="rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs text-[var(--accent-fg)]">{count}</span>}
            </button>;
          })}
        </div>
      </section>
      <section aria-live="polite" className="space-y-3">
        <h3 className="text-lg font-semibold">Deadlines on {new Date(selected + "T12:00:00").toLocaleDateString(undefined, { dateStyle: "long" })}</h3>
        {chosen.length ? <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-4">{chosen.map((a) => <AssignmentRow key={a.id} assignment={a} course={coursesById.get(a.courseId)} href={`/assignments/${a.id}`} />)}</div> : <p className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 text-sm text-[var(--muted)]">No indexed assignment deadlines for this date. This does not indicate whether you have class meetings or personal events.</p>}
      </section>
      <p className="text-xs text-[var(--muted)]">Dates are displayed in your browser&apos;s local time zone. Assignments without a due date are available in the assignments list.</p>
    </div>
  );
}
