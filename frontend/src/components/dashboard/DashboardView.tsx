"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AssignmentRow } from "@/components/assignment/AssignmentRow";
import { ChangeTimeline } from "@/components/changes/ChangeTimeline";
import { MaterialSearchResult } from "@/components/materials/MaterialSearchResult";
import { SemesterRolloverBanner } from "@/components/product/SemesterRolloverBanner";
import { SyncStatus } from "@/components/sync/SyncStatus";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { usePreferences } from "@/contexts/PreferencesContext";
import { MOCK_GREETING_HOUR } from "@/lib/api/mock/data";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { buildStudyWorkspaceUrl, pickDefaultStudyCourseId } from "@/lib/navigation/study-links";
import { courseNavLabel } from "@/lib/product/course-display-name";
import type { Course, DashboardSnapshot } from "@/lib/domain/types";
import { formatDueDate } from "@/lib/utils/date";

export function DashboardView() {
  const api = useAcademicApi();
  const { mode } = useBackendStatus();
  const { displayName } = usePreferences();
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const coursesById = useMemo(() => new Map(courses.map((c) => [c.id, c])), [courses]);

  useEffect(() => {
    let active = true;
    Promise.all([api.getDashboard(), api.getCourses()])
      .then(([dash, c]) => {
        if (!active) return;
        setData(dash);
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
  }, [api, reloadKey]);

  if (loading) return <PageSkeleton />;
  if (error) {
    return (
      <ApiErrorPanel error={error} onRetry={() => { setError(null); setLoading(true); setReloadKey((k) => k + 1); }} />
    );
  }
  if (!data) return <EmptyState title="No dashboard data" />;

  const greeting = `Good ${MOCK_GREETING_HOUR()}, ${displayName}`;
  const continueCourseId = pickDefaultStudyCourseId(courses, data.dueToday, data.thisWeek);
  const continueStudyHref = buildStudyWorkspaceUrl({
    continueSession: true,
    courseId: continueCourseId,
  });

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <SemesterRolloverBanner />
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{greeting}</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {mode === "http"
              ? "Deadlines and changes from your local FastAPI backend."
              : "Preview workspace using mock AcademicApi data."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={buildHeyCanvasUrl({ prompt: "What do I have due today?" })}
            className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)]"
          >
            Ask Hey Canvas
          </Link>
          <Link href="/today" className="rounded-full border border-[var(--border)] px-4 py-2 text-sm">
            Today
          </Link>
          <Link href="/workload" className="rounded-full border border-[var(--border)] px-4 py-2 text-sm">
            Workload
          </Link>
        </div>
      </header>

      <section aria-label="Academic overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Due today", value: data.dueToday.length, detail: "Indexed deadlines", href: "/assignments?window=today" },
          { label: "Due tomorrow", value: data.dueTomorrow.length, detail: "Coming up next", href: "/assignments?window=tomorrow" },
          { label: "This week", value: data.thisWeek.length, detail: "Items in your week", href: "/assignments?window=this_week" },
          { label: "Courses", value: courses.length, detail: "Available in this workspace", href: "/courses" },
        ].map((metric) => (
          <Link key={metric.label} href={metric.href}
            className="group rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 transition hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]">
            <span className="block text-xs font-semibold text-[var(--muted)]">{metric.label}</span>
            <strong className="mt-3 block text-4xl font-semibold tracking-tight">{metric.value}</strong>
            <span className="mt-2 block text-xs text-[var(--muted)]">{metric.detail}</span>
            <span aria-hidden="true" className="mt-3 block text-right text-[var(--accent)]">↗</span>
          </Link>
        ))}
      </section>

      <section
        aria-label="Quick answers"
        className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
      >
        {[
          { label: "Due today", prompt: "What do I have due today?" },
          { label: "Due tomorrow", prompt: "What is due tomorrow?" },
          { label: "What changed", prompt: "What changed since my last sync?" },
        ].map((item) => (
          <Link
            key={item.label}
            href={buildHeyCanvasUrl({ prompt: item.prompt })}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-3 text-sm hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            <span className="font-medium">{item.label}</span>
            <span className="mt-1 block text-xs text-[var(--muted)] line-clamp-2">{item.prompt}</span>
          </Link>
        ))}
        <Link
          href={continueStudyHref}
          className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-3 text-sm hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          <span className="font-medium">Continue studying</span>
          <span className="mt-1 block text-xs text-[var(--muted)] line-clamp-2">
            Resume your backend study session or start a new plan.
          </span>
        </Link>
      </section>

      {data.nextDeadline ? (
        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Next important deadline
          </h3>
          <p className="mt-2 text-lg font-medium">{data.nextDeadline.title}</p>
          <p className="text-sm text-[var(--muted)]">
            {coursesById.get(data.nextDeadline.courseId)
              ? courseNavLabel(coursesById.get(data.nextDeadline.courseId)!)
              : "Course"}{" "}
            ·{" "}
            {formatDueDate(data.nextDeadline.dueAt)}
          </p>
          <div className="mt-3 flex flex-wrap gap-3 text-sm">
            <Link href={`/assignments/${data.nextDeadline.id}`} className="text-[var(--accent)] underline">
              Open assignment
            </Link>
            <Link
              href={buildHeyCanvasUrl({
                courseId: data.nextDeadline.courseId,
                assignmentId: data.nextDeadline.id,
                prompt: `Help me prepare for ${data.nextDeadline.title}`,
              })}
              className="text-[var(--accent)] underline"
            >
              Ask Hey Canvas
            </Link>
          </div>
        </section>
      ) : (
        <EmptyState
          title="No upcoming deadlines"
          description="Nothing is scheduled ahead in the local index. Try Today or Assignments for other windows."
          action={
            <Link href="/assignments" className="text-sm underline">
              Browse assignments
            </Link>
          }
        />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h3 className="mb-2 text-sm font-semibold">Due today</h3>
          <div className="rounded-xl border border-[var(--border)] px-3">
            {data.dueToday.length ? (
              data.dueToday.map((a) => (
                <AssignmentRow key={a.id} assignment={a} course={coursesById.get(a.courseId)} compact />
              ))
            ) : (
              <EmptyState title="Clear for today" />
            )}
          </div>
        </section>
        <section>
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Due tomorrow</h3>
            <Link href="/today" className="text-xs text-[var(--accent)] underline">
              Today view
            </Link>
          </div>
          <div className="rounded-xl border border-[var(--border)] px-3">
            {data.dueTomorrow.length ? (
              data.dueTomorrow.map((a) => (
                <AssignmentRow key={a.id} assignment={a} course={coursesById.get(a.courseId)} compact />
              ))
            ) : (
              <EmptyState title="Nothing due tomorrow" />
            )}
          </div>
        </section>
      </div>

      <section>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">This week</h3>
          <Link href="/assignments?window=this_week" className="text-xs text-[var(--accent)] underline">
            Filter assignments
          </Link>
        </div>
        <div className="rounded-xl border border-[var(--border)] px-3">
          {data.thisWeek.length ? (
            data.thisWeek.map((a) => (
              <AssignmentRow key={a.id} assignment={a} course={coursesById.get(a.courseId)} compact />
            ))
          ) : (
            <EmptyState title="Clear this week" description="No assignments in the this_week window." />
          )}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h3 className="mb-2 text-sm font-semibold">Recent Canvas changes</h3>
          <ChangeTimeline events={data.recentChanges} />
        </section>
        <section className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Suggested materials</h3>
            <Link href="/materials" className="text-xs text-[var(--accent)] underline">
              Search materials
            </Link>
          </div>
          {data.suggestedMaterials.length ? (
            data.suggestedMaterials.map((r) => (
              <MaterialSearchResult key={r.documentId} result={r} />
            ))
          ) : (
            <p className="text-xs text-[var(--muted)]">
              {mode === "http"
                ? "Document suggestions appear when Phase 8 document search is available on the backend."
                : "Try Materials or ask Hey Canvas to search course files in mock mode."}
            </p>
          )}
          <div>
            <h3 className="mb-2 text-sm font-semibold">Sync</h3>
            <SyncStatus variant="sidebar" />
            <Link href="/sync" className="mt-2 inline-block text-xs text-[var(--accent)] underline">
              Sync history
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
