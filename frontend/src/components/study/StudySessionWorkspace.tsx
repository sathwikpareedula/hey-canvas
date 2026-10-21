"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { EvidenceRefButton } from "@/components/study/EvidenceRefButton";
import { ContextualStudyActions } from "@/components/study/ContextualStudyActions";
import { PracticePanel } from "@/components/study/PracticePanel";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { useCourseContext } from "@/contexts/CourseContext";
import { AcademicApiError } from "@/lib/api/errors";
import { mapUiStudyModeToBackend } from "@/lib/api/http/study-workflow-adapters";
import type { Course } from "@/lib/domain/types";
import type { StudySession } from "@/lib/domain/study-workflows";
import { STUDY_MODE_OPTIONS, parseStudyMode, type StudyMode } from "@/lib/domain/study-mode";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { courseNavLabel } from "@/lib/product/course-display-name";

const SESSION_ID_KEY = "hey-canvas-study-session-id";

export function StudySessionWorkspace() {
  const api = useAcademicApi();
  const { mode } = useBackendStatus();
  const { courseId, setCourseId } = useCourseContext();
  const searchParams = useSearchParams();
  const assignmentFromUrl = searchParams.get("assignmentId");
  const shouldContinue = searchParams.get("continue") === "1";
  const courseFromUrl = searchParams.get("courseId");
  const studyModeFromUrl = parseStudyMode(searchParams.get("studyMode"));
  const practiceTopic = searchParams.get("practiceTopic") ?? "";

  useEffect(() => {
    if (courseFromUrl && courseFromUrl !== courseId) setCourseId(courseFromUrl);
  }, [courseFromUrl, courseId, setCourseId]);

  const [studyMode, setStudyMode] = useState<StudyMode>(studyModeFromUrl ?? "learn");

  useEffect(() => {
    if (studyModeFromUrl) queueMicrotask(() => setStudyMode(studyModeFromUrl));
  }, [studyModeFromUrl]);
  const [session, setSession] = useState<StudySession | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const persistSessionId = useCallback((id: string | null) => {
    if (!id) localStorage.removeItem(SESSION_ID_KEY);
    else localStorage.setItem(SESSION_ID_KEY, id);
  }, []);

  const loadSession = useCallback(
    async (sessionId: string, continueFirst = false) => {
      setLoading(true);
      setError(null);
      try {
        const view = continueFirst
          ? await api.continueStudySession(sessionId)
          : await api.getStudySession(sessionId);
        setSession(view);
        persistSessionId(view.sessionId);
      } catch (err) {
        if (err instanceof AcademicApiError && err.kind === "not_found") {
          setNotice("No saved study session on this device. Pick a course and start a new session.");
          setError(null);
        } else {
          setError(err);
        }
        persistSessionId(null);
        setSession(null);
      } finally {
        setLoading(false);
      }
    },
    [api, persistSessionId],
  );

  useEffect(() => {
    api.getCourses().then(setCourses).catch(() => setCourses([]));
  }, [api]);

  const unknownUrlCourse =
    Boolean(courseId && courses.length > 0 && !courses.some((c) => c.id === courseId));
  const resolvedCourseId = unknownUrlCourse ? "" : courseId;

  useEffect(() => {
    const stored = localStorage.getItem(SESSION_ID_KEY);
    if (!stored) {
      if (shouldContinue) {
        queueMicrotask(() =>
          setNotice(
            courseFromUrl || courseId
              ? "No saved session for this browser. Start a new session below."
              : "Choose a course below to continue studying or start a new session.",
          ),
        );
      }
      return;
    }
    queueMicrotask(() => void loadSession(stored, shouldContinue));
  }, [loadSession, shouldContinue, courseFromUrl, courseId, reloadToken]);

  const modeMeta = STUDY_MODE_OPTIONS.find((m) => m.id === studyMode);
  const activeCourse = courses.find((c) => c.id === resolvedCourseId) ?? null;

  const activeStep = useMemo(() => {
    if (!session) return null;
    return session.steps.find((s) => s.status !== "complete") ?? null;
  }, [session]);

  const startSession = async () => {
    if (!resolvedCourseId) {
      setError(new Error("Choose a course before starting a study session."));
      setNotice(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const created = await api.createStudySession({
        courseId: resolvedCourseId,
        goal: modeMeta?.label ?? "Study session",
        durationMinutes: 45,
        topics: modeMeta ? [modeMeta.label] : [],
        studyMode: mapUiStudyModeToBackend(studyMode),
        assignmentIds: assignmentFromUrl ? [assignmentFromUrl] : [],
      });
      setSession(created);
      persistSessionId(created.sessionId);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const completeStep = async (order: number) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.advanceStudySession(session.sessionId, order);
      setSession(updated);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const uiStudyMode: StudyMode =
    session?.studyMode === "exam_prep" ? "exam" : (session?.studyMode as StudyMode) ?? studyMode;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">
            Study session{activeCourse ? ` · ${courseNavLabel(activeCourse)}` : ""}
          </h1>
          {studyMode === "exam" ? (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="rounded bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200 text-xs px-2 py-0.5 font-medium">
                Exam prep
              </span>
              <p className="text-sm text-[var(--muted)]">
                Targeted exam preparation and practice grounded in course syllabus and materials.
              </p>
            </div>
          ) : (
            <p className="mt-1 text-sm text-[var(--muted)]">
              {mode === "http"
                ? "Sessions are stored by your academic backend and can be continued from the dashboard."
                : "Mock study sessions use local sample planning."}
            </p>
          )}
        </div>
        <Link href="/study/guide" className="text-sm text-[var(--accent)] underline">
          Study guide
        </Link>
      </header>

      {unknownUrlCourse ? (
        <p className="rounded-lg border border-[var(--warn-border)] bg-[var(--warn-bg)] px-3 py-2 text-sm" role="status">
          That course link is not in your local catalog. Choose a course below.
        </p>
      ) : null}

      {!resolvedCourseId ? (
        <div className="rounded-lg border border-[var(--warn-border)] bg-[var(--warn-bg)] px-3 py-3 text-sm space-y-2">
          <p>Select a course so study sessions attach to the right Canvas course.</p>
          <label className="sr-only" htmlFor="study-course-select">Course</label>
          <select
            id="study-course-select"
            className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm"
            value=""
            onChange={(e) => {
              if (e.target.value) setCourseId(e.target.value);
            }}
          >
            <option value="">Choose course…</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{courseNavLabel(c)}</option>
            ))}
          </select>
        </div>
      ) : null}

      {notice ? (
        <p className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--muted)]" role="status">
          {notice}
        </p>
      ) : null}

      {resolvedCourseId && activeCourse ? (
        <section aria-label="Study shortcuts">
          <h2 className="mb-2 text-sm font-semibold">Quick study actions</h2>
          <ContextualStudyActions
            courseId={resolvedCourseId}
            courseName={courseNavLabel(activeCourse)}
            assignmentId={assignmentFromUrl ?? undefined}
            layout="chips"
          />
        </section>
      ) : null}

      <section className="rounded-xl border border-[var(--border)] p-4 space-y-3">
        <h2 className="text-sm font-semibold">Mode</h2>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Study session mode">
          {STUDY_MODE_OPTIONS.map((m) => (
            <button
              key={m.id}
              type="button"
              aria-pressed={studyMode === m.id}
              onClick={() => setStudyMode(m.id)}
              disabled={Boolean(session)}
              className={`min-h-9 rounded-full px-3 py-1 text-sm ${
                studyMode === m.id
                  ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                  : "border border-[var(--border)]"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        {modeMeta ? <p className="text-xs text-[var(--muted)]">{modeMeta.description}</p> : null}
        <button
          type="button"
          disabled={loading}
          onClick={() => void startSession()}
          className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] disabled:opacity-50"
        >
          {session ? "Start new session" : "Start session"}
        </button>
      </section>

      {error ? (
        <ApiErrorPanel
          error={error}
          onRetry={() => {
            setError(null);
            const stored = localStorage.getItem(SESSION_ID_KEY);
            if (stored) {
              setReloadToken((n) => n + 1);
              void loadSession(stored, shouldContinue);
            } else {
              void startSession();
            }
          }}
        />
      ) : null}

      {session ? (
        <section className="rounded-xl border border-[var(--border)] p-4" aria-label="Session plan">
          <h2 className="text-sm font-semibold">Plan</h2>
          <p className="text-xs text-[var(--muted)] break-words">
            {session.goal} · {session.progress}% complete · {session.status}
          </p>
          {session.relevantEvidence.length ? (
            <ul className="mt-2 space-y-1">
              {session.relevantEvidence.map((ev, i) => (
                <li key={i}>
                  <EvidenceRefButton evidence={ev} courseId={session.courseId} />
                </li>
              ))}
            </ul>
          ) : null}
          <ol className="mt-3 space-y-2">
            {session.steps.map((step) => {
              const done = step.status === "complete";
              const targetCourse = activeCourse ? courseNavLabel(activeCourse) : "this course";
              const isExam = session.studyMode === "exam_prep" || studyMode === "exam";
              const prompt = isExam
                ? `Help me prepare for my exam in ${targetCourse} on topic "${step.title}". Use only evidence from the course, and say clearly when course material is unavailable.`
                : `Help me with the active ${session.studyMode.replace("_", " ")} study step "${step.title}" for my current session in ${targetCourse}. Use only evidence from the selected course, and say clearly when course material is unavailable.`;
              return (
                <li
                  key={step.order}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border)] px-3 py-2"
                >
                  <span className={done ? "text-[var(--muted)] line-through" : "font-medium"}>
                    {step.title}
                    <span className="ml-2 text-xs text-[var(--muted)]">{step.minutes} min</span>
                  </span>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={buildHeyCanvasUrl({
                        courseId: session.courseId,
                        studyMode: uiStudyMode,
                        assignmentId: session.assignmentIds[0],
                        prompt,
                      })}
                      className="text-xs text-[var(--accent)] underline"
                    >
                      Ask Hey Canvas
                    </Link>
                    {!done ? (
                      <button
                        type="button"
                        disabled={loading}
                        onClick={() => void completeStep(step.order)}
                        className="text-xs underline"
                      >
                        Mark done
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
          {activeStep ? (
            <p className="mt-3 text-sm text-[var(--muted)]" role="status">
              Current step: <span className="text-[var(--foreground)]">{activeStep.title}</span>
            </p>
          ) : (
            <p className="mt-3 text-sm text-[var(--muted)]">Session complete.</p>
          )}
        </section>
      ) : loading ? (
        <p className="text-sm text-[var(--muted)]" role="status">Loading session…</p>
      ) : null}

      {!session && !loading && resolvedCourseId ? (
        <p className="text-sm text-[var(--muted)]">
          No active backend session — start one above or use Continue studying from the dashboard.
        </p>
      ) : null}

      {resolvedCourseId ? (
        <PracticePanel courseId={resolvedCourseId} initialTopic={practiceTopic} />
      ) : null}
    </div>
  );
}
