"use client";

import Link from "next/link";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { useEffect, useMemo, useState } from "react";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { AssignmentRow } from "@/components/assignment/AssignmentRow";
import { CourseBadge } from "@/components/course/CourseBadge";
import { ChangeTimeline } from "@/components/changes/ChangeTimeline";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { AcademicApiNotImplementedError } from "@/lib/api/errors";
import { CourseChatPanel } from "@/components/courses/CourseChatPanel";
import { CourseProfileSettings } from "@/components/courses/CourseProfileSettings";
import { ContextualStudyActions } from "@/components/study/ContextualStudyActions";
import { buildStudyWorkspaceUrl } from "@/lib/navigation/study-links";
import { STUDY_MODE_OPTIONS } from "@/lib/domain/study-mode";
import type {
  Assignment,
  ChangeEvent,
  Course,
  DocumentCoverageSummary,
  DocumentSearchResult,
  Module,
  ModuleItem,
} from "@/lib/domain/types";
import { MaterialSearchResult } from "@/components/materials/MaterialSearchResult";
import { pickNextDeadline, filterUpcomingAssignments } from "@/lib/assignments/deadline-selection";
import { coursePrimaryTitle } from "@/lib/courses/display";
import { formatDueDate } from "@/lib/utils/date";

type Tab = "overview" | "chat" | "assignments" | "materials" | "study";

export function CourseWorkspace({ courseId }: { courseId: string }) {
  const api = useAcademicApi();
  const [tab, setTab] = useState<Tab>("overview");
  const [course, setCourse] = useState<Course | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [items, setItems] = useState<ModuleItem[]>([]);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [coverage, setCoverage] = useState<DocumentCoverageSummary | null>(null);
  const [materialQuery, setMaterialQuery] = useState("");
  const debouncedMaterialQuery = useDebouncedValue(materialQuery, 250);
  const [modulesNote, setModulesNote] = useState<string | null>(null);
  const [materialSearchCache, setMaterialSearchCache] = useState<{
    key: string;
    rows: DocumentSearchResult[];
  }>({ key: "", rows: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [c, a, ch, cov] = await Promise.all([
          api.getCourse(courseId),
          api.getAssignments({ courseId }),
          api.getChanges(20),
          api.getDocumentCoverage ? api.getDocumentCoverage(courseId).catch(() => null) : Promise.resolve(null),
        ]);
        let m: Module[] = [];
        let mi: ModuleItem[] = [];
        try {
          m = await api.getModules(courseId);
          mi = await api.getModuleItems(courseId);
        } catch (err) {
          if (err instanceof AcademicApiNotImplementedError) {
            setModulesNote("Module browsing is not available in HTTP mode yet.");
          } else {
            throw err;
          }
        }
        if (!active) return;
        setCourse(c);
        setAssignments(a);
        setModules(m);
        setItems(mi);
        setChanges(ch.filter((e) => e.courseId === courseId).slice(0, 5));
        setCoverage(cov);
        setLoading(false);
      } catch (err) {
        if (!active) return;
        setError(err);
        setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [api, courseId]);

  const materialSearchKey =
    debouncedMaterialQuery.trim().length >= 2
      ? `${courseId}:${debouncedMaterialQuery.trim()}`
      : "";
  const materialSearchLoading =
    Boolean(materialSearchKey) && materialSearchCache.key !== materialSearchKey;
  const indexedMaterialHits =
    materialSearchCache.key === materialSearchKey ? materialSearchCache.rows : [];

  useEffect(() => {
    if (!materialSearchKey) return;
    const q = debouncedMaterialQuery.trim();
    let active = true;
    api
      .searchDocuments({ query: q, courseId })
      .then((rows) => {
        if (!active) return;
        setMaterialSearchCache({ key: materialSearchKey, rows });
      })
      .catch(() => {
        if (!active) return;
        setMaterialSearchCache({ key: materialSearchKey, rows: [] });
      });
    return () => {
      active = false;
    };
  }, [api, courseId, debouncedMaterialQuery, materialSearchKey]);

  const nextDeadline = useMemo(() => pickNextDeadline(assignments), [assignments]);

  const upcoming = useMemo(() => filterUpcomingAssignments(assignments, new Date(), 5), [assignments]);

  if (loading) return <LoadingState />;
  if (error) return <ApiErrorPanel error={error} />;
  if (!course) {
    return (
      <EmptyState
        title="Course not found"
        description="This course id is not in the local academic index."
        action={
          <Link href="/courses" className="text-sm text-[var(--accent)] underline">
            Back to courses
          </Link>
        }
      />
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "chat", label: "Chat" },
    { id: "assignments", label: "Assignments" },
    { id: "materials", label: "Materials" },
    { id: "study", label: "Study" },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <CourseBadge course={course} />
          <h2 className="mt-2 text-xl font-semibold break-words">{coursePrimaryTitle(course)}</h2>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Link
            href={buildStudyWorkspaceUrl({ courseId, continueSession: true })}
            className="rounded-full border border-[var(--border)] px-4 py-2 text-sm"
          >
            Continue studying
          </Link>
          <Link
            href={buildHeyCanvasUrl({
              courseId,
              prompt: `What should I focus on in ${course.name} this week?`,
            })}
            className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)]"
          >
            Hey Canvas
          </Link>
        </div>
      </div>
      <div role="tablist" aria-label="Course sections" className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            aria-controls={`course-panel-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`rounded-full px-3 py-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
              tab === t.id
                ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                : "border border-[var(--border)] text-[var(--muted)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "chat" ? (
        <div id="course-panel-chat" role="tabpanel">
          <CourseChatPanel key={course.id} course={course} />
        </div>
      ) : null}

      {tab === "overview" ? (
        <div id="course-panel-overview" role="tabpanel" className="space-y-6">
          {nextDeadline ? (
            <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                Next deadline
              </h3>
              <p className="mt-2 font-medium break-words">{nextDeadline.title}</p>
              <p className="text-sm text-[var(--muted)]">{formatDueDate(nextDeadline.dueAt)}</p>
              <div className="mt-3 flex flex-wrap gap-3 text-sm">
                <Link href={`/assignments/${nextDeadline.id}`} className="text-[var(--accent)] underline">
                  Open assignment
                </Link>
                <Link
                  href={buildHeyCanvasUrl({
                    courseId,
                    assignmentId: nextDeadline.id,
                    prompt: `Help me plan for ${nextDeadline.title}`,
                  })}
                  className="text-[var(--accent)] underline"
                >
                  Ask Hey Canvas
                </Link>
              </div>
            </section>
          ) : null}
          <section>
            <h3 className="text-sm font-semibold">Upcoming work</h3>
            <div className="mt-2 rounded-xl border border-[var(--border)] px-3">
              {upcoming.length ? (
                upcoming.map((a) => (
                  <AssignmentRow
                    key={a.id}
                    assignment={a}
                    course={course}
                    href={`/assignments/${a.id}`}
                  />
                ))
              ) : (
                <EmptyState title="No upcoming items" />
              )}
            </div>
          </section>
          <section>
            <h3 className="text-sm font-semibold">Recent changes</h3>
            <div className="mt-2">
              <ChangeTimeline events={changes} />
            </div>
          </section>
        </div>
      ) : null}

      {tab === "assignments" ? (
        <div id="course-panel-assignments" role="tabpanel" className="rounded-xl border border-[var(--border)] px-3">
          {assignments.map((a) => (
            <AssignmentRow key={a.id} assignment={a} course={course} href={`/assignments/${a.id}`} />
          ))}
        </div>
      ) : null}

      {tab === "materials" ? (
        <div id="course-panel-materials" role="tabpanel" className="space-y-4">
          {coverage ? (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-xs uppercase tracking-wide text-[var(--muted)]">
                  Knowledge Indexing Status
                </span>
                {coverage.eligible_files > 0 &&
                coverage.indexed_current >= coverage.eligible_files &&
                coverage.awaiting_download === 0 &&
                coverage.indexed_stale === 0 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    All materials indexed ({coverage.indexed_current} of {coverage.eligible_files} ready)
                  </span>
                ) : coverage.eligible_files > 0 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                    Preparation pending ({coverage.indexed_current} of {coverage.eligible_files} ready)
                  </span>
                ) : (
                  <span className="text-xs text-[var(--muted)]">No eligible files</span>
                )}
              </div>
              <div className="mt-2 text-xs text-[var(--muted)] flex flex-wrap gap-x-4 gap-y-1">
                <span>Known files: {coverage.known_files}</span>
                <span>Eligible: {coverage.eligible_files}</span>
                <span>Current index: {coverage.indexed_current}</span>
                {coverage.indexed_stale > 0 ? <span>Stale: {coverage.indexed_stale}</span> : null}
                {coverage.awaiting_download > 0 ? <span>Awaiting download: {coverage.awaiting_download}</span> : null}
                {coverage.needs_ocr > 0 ? <span>Needs OCR: {coverage.needs_ocr}</span> : null}
                {coverage.failed > 0 ? <span className="text-red-500">Failed: {coverage.failed}</span> : null}
              </div>
              {coverage.eligible_files > coverage.indexed_current ? (
                <p className="mt-2 text-xs text-[var(--muted)]">
                  Metadata synchronized from Canvas. Document text preparation and indexing are pending for remaining files.
                </p>
              ) : null}
            </div>
          ) : null}
          {modulesNote ? <p className="text-xs text-[var(--muted)]">{modulesNote}</p> : null}
          <label className="block text-sm">
            <span className="text-[var(--muted)]">Filter module items</span>
            <input
              type="search"
              value={materialQuery}
              onChange={(e) => setMaterialQuery(e.target.value)}
              placeholder="Search course materials and modules…"
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            />
          </label>
          {materialSearchLoading ? (
            <LoadingState label="Searching indexed materials…" />
          ) : null}
          {indexedMaterialHits.length > 0 ? (
            <ul className="space-y-2">
              {indexedMaterialHits.map((hit) => (
                <li key={hit.documentId}>
                  <MaterialSearchResult result={hit} query={debouncedMaterialQuery} />
                </li>
              ))}
            </ul>
          ) : null}
          {modules.length ? (
            <ul className="space-y-2">
              {modules.map((mod) => (
                <li key={mod.id} className="rounded-xl border border-[var(--border)] p-3">
                  <p className="text-sm font-medium break-words">{mod.name}</p>
                  <ul className="mt-2 space-y-1 text-sm text-[var(--muted)]">
                    {items
                      .filter((i) => i.moduleId === mod.id)
                      .filter((i) =>
                        debouncedMaterialQuery
                          ? i.title.toLowerCase().includes(debouncedMaterialQuery.toLowerCase())
                          : true,
                      )
                      .map((i) => (
                        <li key={i.id} className="break-words">
                          <Link
                            href={`/materials?q=${encodeURIComponent(i.title)}&course=${courseId}`}
                            className="underline"
                          >
                            {i.title}
                          </Link>
                        </li>
                      ))}
                  </ul>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No module materials indexed"
              description="Use the Materials page or sync more course files through the backend CLI."
              action={
                <Link href={`/materials?course=${courseId}`} className="text-sm underline">
                  Browse materials
                </Link>
              }
            />
          )}
        </div>
      ) : null}

      {tab === "study" ? (
        <div id="course-panel-study" role="tabpanel" className="space-y-4">
          <CourseProfileSettings courseId={courseId} />
          <p className="text-sm text-[var(--muted)]">
            Study sessions stay tied to this course — your
            global course context is unchanged until you change it elsewhere.
          </p>
          <ContextualStudyActions courseId={courseId} courseName={course.name} />
          <p className="text-sm text-[var(--muted)]">Or open Hey Canvas in a study mode:</p>
          <ul className="flex flex-col gap-2">
            {STUDY_MODE_OPTIONS.map((mode) => (
              <li key={mode.id}>
                <Link
                  href={buildHeyCanvasUrl({
                    courseId,
                    studyMode: mode.id,
                    prompt: `Help me ${mode.label.toLowerCase()} for ${course.name}.`,
                  })}
                  className="block rounded-xl border border-[var(--border)] px-4 py-3 text-sm hover:border-[var(--accent)]"
                >
                  <span className="font-medium">{mode.label}</span>
                  <span className="mt-1 block text-xs text-[var(--muted)]">{mode.description}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
