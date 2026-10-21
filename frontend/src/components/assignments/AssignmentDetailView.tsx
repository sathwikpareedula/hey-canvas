"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChangeTimeline } from "@/components/changes/ChangeTimeline";
import { CourseBadge } from "@/components/course/CourseBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { AssignmentPlanningActions } from "@/components/planning/AssignmentPlanningActions";
import { ContextualStudyActions } from "@/components/study/ContextualStudyActions";
import { HeyCanvasActionLinks } from "@/components/ui/HeyCanvasActionLinks";
import { assignmentHeyCanvasActions } from "@/lib/navigation/hey-canvas-actions";
import type { AssignmentDetail, ChangeEvent, Course } from "@/lib/domain/types";
import { deadlineWindowLabel, formatDueDate } from "@/lib/utils/date";

export function AssignmentDetailView({ assignmentId }: { assignmentId: string }) {
  const api = useAcademicApi();
  const [assignment, setAssignment] = useState<AssignmentDetail | null | undefined>(undefined);
  const [course, setCourse] = useState<Course | null>(null);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    api
      .getAssignment(assignmentId)
      .then(async (a) => {
        if (!active) return;
        if (!a) {
          setAssignment(null);
          setLoading(false);
          return;
        }
        setAssignment(a);
        const [c, ch] = await Promise.all([
          api.getCourse(a.courseId),
          api.getChanges(20),
        ]);
        if (!active) return;
        setCourse(c);
        setChanges(
          ch.filter((e) => a.recentChangeIds?.includes(e.id) || e.entityLabel.includes(a.title.slice(0, 12))),
        );
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
  }, [api, assignmentId]);

  if (loading) return <PageSkeleton />;
  if (error) return <ApiErrorPanel error={error} />;
  if (assignment === null) {
    return (
      <EmptyState
        title="Assignment not found"
        description="Unknown assignment id."
        action={<Link href="/assignments" className="text-sm underline">Back to assignments</Link>}
      />
    );
  }
  if (!assignment) return null;

  const status = deadlineWindowLabel(assignment.deadlineWindow);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        {course ? <CourseBadge course={course} /> : null}
        <h2 className="mt-2 text-xl font-semibold break-words">{assignment.title}</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {formatDueDate(assignment.dueAt)}
          {assignment.pointsPossible != null ? ` · ${assignment.pointsPossible} pts` : ""}
          {assignment.workflowState ? ` · ${assignment.workflowState}` : ""}
        </p>
        {status ? (
          <span className="mt-2 inline-block rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs">
            {status}
          </span>
        ) : null}
      </header>

      {assignment.moduleContext ? (
        <p className="text-sm text-[var(--muted)]">Module: {assignment.moduleContext}</p>
      ) : null}

      <section>
        <h3 className="text-sm font-semibold">Description</h3>
        <pre className="mt-2 whitespace-pre-wrap rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm font-sans">
          {assignment.descriptionPlainText || "No description available."}
        </pre>
      </section>

      <AssignmentPlanningActions
        courseId={assignment.courseId}
        assignmentId={assignment.id}
        assignmentTitle={assignment.title}
      />

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Study &amp; practice</h3>
        <ContextualStudyActions
          layout="chips"
          courseId={assignment.courseId}
          courseName={course?.name}
          assignmentId={assignment.id}
          assignmentTitle={assignment.title}
        />
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Hey Canvas</h3>
        <p className="text-xs text-[var(--muted)]">
          Opens Hey Canvas with this assignment in context. Nothing is submitted to Canvas.
        </p>
        <HeyCanvasActionLinks
          primaryId="explain"
          actions={assignmentHeyCanvasActions(assignment.title, {
            assignmentId: assignment.id,
            courseId: assignment.courseId,
          })}
        />
      </section>

      {assignment.relatedDocumentIds?.length ? (
        <section>
          <h3 className="text-sm font-semibold">Related materials</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {assignment.relatedDocumentIds.map((id) => (
              <li key={id}>
                <Link href={`/materials/${id}`} className="text-[var(--accent)] underline">
                  Open material {id} (sample)
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {changes.length ? (
        <section>
          <h3 className="text-sm font-semibold">Recent changes</h3>
          <ChangeTimeline events={changes.slice(0, 3)} />
        </section>
      ) : null}
    </div>
  );
}
