"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { Course } from "@/lib/domain/types";
import { buildStudyWorkspaceUrl } from "@/lib/navigation/study-links";
import { EvidenceRefButton } from "@/components/study/EvidenceRefButton";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useCourseContext } from "@/contexts/CourseContext";
import type { StudyGuide } from "@/lib/domain/study-workflows";

export function StudyGuideView() {
  const api = useAcademicApi();
  const { courseId: ctxCourseId, setCourseId } = useCourseContext();
  const searchParams = useSearchParams();
  const [topic, setTopic] = useState(searchParams.get("topic") ?? "");
  const [assignmentId, setAssignmentId] = useState(searchParams.get("assignmentId") ?? "");
  const [documentId, setDocumentId] = useState(searchParams.get("documentId") ?? "");
  const courseFromUrl = searchParams.get("courseId");
  const courseId = courseFromUrl ?? ctxCourseId ?? "";
  const [courses, setCourses] = useState<Course[]>([]);
  const [guide, setGuide] = useState<StudyGuide | null>(null);

  useEffect(() => {
    api.getCourses().then(setCourses).catch(() => setCourses([]));
  }, [api]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const build = async () => {
    if (!courseId) {
      setError(new Error("Select a course before building a study guide."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setGuide(
        await api.buildStudyGuide({
          courseId,
          topic: topic || undefined,
          assignmentId: assignmentId || undefined,
          documentId: documentId || undefined,
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 print:max-w-none">
      <header className="flex flex-wrap items-end justify-between gap-2 print:hidden">
        <div>
          <h1 className="text-xl font-semibold">Study guide</h1>
          <p className="text-sm text-[var(--muted)]">
            Structured guide from your local academic backend — grounded where evidence is available.
          </p>
        </div>
        <Link
          href={buildStudyWorkspaceUrl({ courseId: courseId || undefined, assignmentId: assignmentId || undefined })}
          className="text-sm text-[var(--accent)] underline"
        >
          Return to study session
        </Link>
      </header>
      <section className="space-y-2 rounded-xl border border-[var(--border)] p-4 print:hidden">
        <label className="block text-sm">
          Course
          <select
            value={courseId}
            disabled={Boolean(ctxCourseId && !courseFromUrl)}
            onChange={(e) => setCourseId(e.target.value || null)}
            className="mt-1 w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          >
            <option value="">Choose course…</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Topic (optional)
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            placeholder="Assignment ID (optional)"
            value={assignmentId}
            onChange={(e) => setAssignmentId(e.target.value)}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
          <input
            placeholder="Document ID (optional)"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => void build()}
          className="min-h-10 rounded-full bg-[var(--accent)] px-4 text-sm text-[var(--accent-fg)]"
        >
          {busy ? "Building…" : "Build study guide"}
        </button>
        {error ? <ApiErrorPanel error={error} /> : null}
      </section>
      {guide ? (
        <article className="study-guide-print space-y-6 rounded-xl border border-[var(--border)] p-6">
          <header>
            <h2 className="text-lg font-semibold break-words">{guide.title}</h2>
            <p className="mt-2 text-sm text-[var(--muted)] break-words">{guide.scope}</p>
          </header>
          {guide.keyConcepts.length ? (
            <section>
              <h3 className="text-sm font-semibold">Key concepts</h3>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {guide.keyConcepts.map((c, i) => (
                  <li key={i} className="break-words">{c}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {guide.explanations.length ? (
            <section>
              <h3 className="text-sm font-semibold">Explanations</h3>
              <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
                {guide.explanations.map((e, i) => (
                  <li key={i} className="break-words">{e}</li>
                ))}
              </ol>
            </section>
          ) : null}
          <section>
            <h3 className="text-sm font-semibold">Professor evidence</h3>
            {guide.evidence.length ? (
              <ul className="mt-2 space-y-1">
                {guide.evidence.map((ev, i) => (
                  <li key={i}>
                    <EvidenceRefButton evidence={ev} courseId={courseId} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-[var(--muted)]">
                No material evidence was attached. Try building with a document ID or ask Hey Canvas
                after syncing professor materials.
              </p>
            )}
          </section>
          {guide.reviewChecklist.length ? (
            <section>
              <h3 className="text-sm font-semibold">Review checklist</h3>
              <ul className="mt-2 space-y-1 text-sm">
                {guide.reviewChecklist.map((item, i) => (
                  <li key={i} className="flex gap-2 break-words">
                    <span aria-hidden>☐</span>
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {guide.practicePrompts.length ? (
            <section>
              <h3 className="text-sm font-semibold">Practice prompts</h3>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {guide.practicePrompts.map((p, i) => (
                  <li key={i} className="break-words">{p}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {guide.uncertainties.length ? (
            <section>
              <h3 className="text-sm font-semibold">Uncertainties</h3>
              <ul className="mt-2 list-disc pl-5 text-sm text-[var(--muted)]">
                {guide.uncertainties.map((u, i) => (
                  <li key={i} className="break-words">{u}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
