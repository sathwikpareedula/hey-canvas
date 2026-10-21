"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ContextChip } from "@/components/hey-canvas/ContextChip";
import { EntityDisambiguationCard } from "@/components/product/EntityDisambiguationCard";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { ResolvedCourse } from "@/lib/domain/course-intelligence";
import { useCourseContext } from "@/contexts/CourseContext";
import { STUDY_MODE_OPTIONS, parseStudyMode } from "@/lib/domain/study-mode";
import { removeSearchParams } from "@/lib/navigation/search-params";

export function AcademicContextBar({
  courses,
}: {
  courses: { id: string; name: string }[];
}) {
  const { courseId, setCourseId } = useCourseContext();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const assignmentId = searchParams.get("assignmentId");
  const documentId = searchParams.get("documentId");
  const studyMode = parseStudyMode(searchParams.get("studyMode"));
  const [assignmentMeta, setAssignmentMeta] = useState<{
    id: string;
    title: string | null;
  } | null>(null);
  const [documentMeta, setDocumentMeta] = useState<{
    id: string;
    title: string | null;
  } | null>(null);
  const api = useAcademicApi();
  const [routingNote, setRoutingNote] = useState<string | null>(null);
  const [routingCandidates, setRoutingCandidates] = useState<ResolvedCourse[]>([]);

  useEffect(() => {
    let active = true;
    api
      .resolveCourseRouter({
        courseId: courseId ?? undefined,
        assignmentId: assignmentId ?? undefined,
        documentId: documentId ?? undefined,
        activeCourseId: courseId ?? undefined,
      })
      .then((result) => {
        if (!active) return;
        if (result.outcome === "ambiguous") {
          setRoutingNote("Which course did you mean?");
          setRoutingCandidates(result.candidates);
        } else if (result.outcome === "unresolved" && (assignmentId || documentId)) {
          setRoutingNote("Course context is unclear — select a course.");
          setRoutingCandidates(result.candidates);
        } else {
          setRoutingNote(null);
          setRoutingCandidates([]);
        }
      })
      .catch(() => {
        if (active) setRoutingNote(null);
      });
    return () => {
      active = false;
    };
  }, [api, courseId, assignmentId, documentId]);

  useEffect(() => {
    if (!assignmentId) return;
    let active = true;
    api
      .getAssignment(assignmentId)
      .then((a) => {
        if (active) {
          setAssignmentMeta({ id: assignmentId, title: a?.title ?? "Unavailable" });
        }
      })
      .catch(() => {
        if (active) setAssignmentMeta({ id: assignmentId, title: "Unavailable" });
      });
    return () => {
      active = false;
    };
  }, [api, assignmentId]);

  useEffect(() => {
    if (!documentId) return;
    let active = true;
    api
      .getDocument(documentId)
      .then((d) => {
        if (active) {
          setDocumentMeta({ id: documentId, title: d?.title ?? "Unavailable" });
        }
      })
      .catch(() => {
        if (active) setDocumentMeta({ id: documentId, title: "Unavailable" });
      });
    return () => {
      active = false;
    };
  }, [api, documentId]);

  const activeCourse = courses.find((c) => c.id === courseId);
  const assignmentTitle =
    assignmentMeta?.id === assignmentId ? assignmentMeta.title : null;
  const documentTitle =
    documentMeta?.id === documentId ? documentMeta.title : null;
  const studyLabel = STUDY_MODE_OPTIONS.find((m) => m.id === studyMode)?.label;

  const clearStudyMode = () => {
    router.replace(removeSearchParams(pathname, searchParams, ["studyMode"]));
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2 text-sm">
      {routingCandidates.length > 0 ? (
        <EntityDisambiguationCard
          title={routingNote ?? "Which did you mean?"}
          candidates={routingCandidates.map((c) => ({
            id: c.courseId,
            kind: "course" as const,
            title: c.courseName ?? c.courseCode ?? "Course",
            subtitle: c.courseCode,
            courseId: c.courseId,
          }))}
          onPick={(candidate) => setCourseId(candidate.id)}
        />
      ) : routingNote ? (
        <p
          className="rounded-md border border-[var(--warn-border)] bg-[var(--warn-bg)] px-2 py-1 text-xs text-[var(--warn-text)]"
          role="status"
        >
          {routingNote}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <span className="shrink-0 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Context
        </span>
        {activeCourse ? (
          <ContextChip
            label={activeCourse.name}
            removeLabel={`Remove course context ${activeCourse.name}`}
            onRemove={() => setCourseId(null)}
          />
        ) : (
          <span className="text-xs text-[var(--muted)]">
            {studyMode || assignmentId || documentId
              ? "Select a course for course-specific answers"
              : "No course selected"}
          </span>
        )}
        <label className="sr-only" htmlFor="hey-canvas-course-select">
          Course context
        </label>
        <select
          id="hey-canvas-course-select"
          value={courseId ?? ""}
          onChange={(e) => setCourseId(e.target.value || null)}
          className="max-w-[min(100%,16rem)] truncate rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          <option value="">Choose course…</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        {assignmentId ? (
          <ContextChip
            label={assignmentTitle ? `Assignment: ${assignmentTitle}` : "Assignment"}
            removeLabel="Remove assignment context"
            onRemove={() =>
              router.replace(
                removeSearchParams(pathname, searchParams, ["assignmentId", "prompt"]),
              )
            }
          />
        ) : null}
        {documentId ? (
          <ContextChip
            label={documentTitle ? `Material: ${documentTitle}` : "Material"}
            removeLabel="Remove material context"
            onRemove={() =>
              router.replace(
                removeSearchParams(pathname, searchParams, ["documentId", "prompt"]),
              )
            }
          />
        ) : null}
        {studyLabel ? (
          <ContextChip
            label={`Study: ${studyLabel}`}
            removeLabel="Clear study mode"
            onRemove={clearStudyMode}
          />
        ) : null}
      </div>
    </div>
  );
}
