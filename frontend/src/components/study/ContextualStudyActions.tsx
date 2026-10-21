"use client";

import Link from "next/link";
import { STUDY_MODE_OPTIONS, type StudyMode } from "@/lib/domain/study-mode";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { buildStudyGuideUrl, buildStudyWorkspaceUrl } from "@/lib/navigation/study-links";

export function ContextualStudyActions({
  courseId,
  courseName,
  assignmentId,
  assignmentTitle,
  documentId,
  materialTitle,
  layout = "list",
}: {
  courseId: string;
  courseName?: string;
  assignmentId?: string;
  assignmentTitle?: string;
  documentId?: string;
  materialTitle?: string;
  layout?: "list" | "chips";
}) {
  const label = courseName ?? "this course";
  const topic = assignmentTitle ?? materialTitle ?? label;

  const modes: { mode: StudyMode; action: string }[] = [
    { mode: "learn", action: "Study" },
    { mode: "review", action: "Review" },
    { mode: "practice", action: "Practice" },
    { mode: "exam", action: "Exam prep" },
  ];

  const items = [
    ...modes.map(({ mode, action }) => ({
      key: `study-${mode}`,
      label: `${action} ${assignmentTitle ? "this assignment" : documentId ? "this material" : label}`,
      href: buildStudyWorkspaceUrl({
        courseId,
        studyMode: mode,
        assignmentId,
        documentId,
      }),
    })),
    {
      key: "continue",
      label: "Continue studying",
      href: buildStudyWorkspaceUrl({ courseId, continueSession: true, assignmentId }),
    },
    {
      key: "guide",
      label: "Create study guide",
      href: buildStudyGuideUrl({
        courseId,
        topic,
        assignmentId,
        documentId,
      }),
    },
    {
      key: "hey-explain",
      label: "Explain with Hey Canvas",
      href: buildHeyCanvasUrl({
        courseId,
        assignmentId,
        documentId,
        prompt: documentId
          ? `Explain “${materialTitle ?? "this material"}” using professor materials.`
          : assignmentId
            ? `Explain “${assignmentTitle ?? "this assignment"}” using professor materials.`
            : `Help me study ${label} with professor materials.`,
      }),
    },
    {
      key: "hey-practice",
      label: "Practice with Hey Canvas",
      href: buildHeyCanvasUrl({
        courseId,
        assignmentId,
        documentId,
        studyMode: "practice",
        prompt: `Give me generated practice questions about ${topic}. Label them as practice only.`,
      }),
    },
  ];

  if (layout === "chips") {
    return (
      <div className="flex flex-wrap gap-2" role="list" aria-label="Study actions">
        {items.map((item) => (
          <Link
            key={item.key}
            role="listitem"
            href={item.href}
            className="min-h-9 rounded-full border border-[var(--border)] px-3 py-1 text-xs hover:border-[var(--accent)]"
          >
            {item.label}
          </Link>
        ))}
      </div>
    );
  }

  return (
    <ul className="space-y-2" aria-label="Study actions">
      {items.map((item) => (
        <li key={item.key}>
          <Link
            href={item.href}
            className="block rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:border-[var(--accent)] break-words"
          >
            {item.label}
          </Link>
        </li>
      ))}
      <li className="text-xs text-[var(--muted)]">
        Modes: {STUDY_MODE_OPTIONS.map((m) => m.label).join(" · ")}
      </li>
    </ul>
  );
}
