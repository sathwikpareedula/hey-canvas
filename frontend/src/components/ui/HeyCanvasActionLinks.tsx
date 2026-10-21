import Link from "next/link";
import type { StudyMode } from "@/lib/domain/study-mode";
import { heyCanvasActionHref, type HeyCanvasAction } from "@/lib/navigation/hey-canvas-actions";

export function HeyCanvasActionLinks({
  actions,
  studyMode,
  primaryId,
}: {
  actions: (HeyCanvasAction & {
    assignmentId?: string;
    documentId?: string;
    courseId?: string;
  })[];
  studyMode?: StudyMode;
  primaryId?: string;
}) {
  return (
    <ul className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
      {actions.map((action) => {
        const primary = action.id === primaryId;
        return (
          <li key={action.id} className="min-w-0 flex-1 sm:flex-none">
            <Link
              href={heyCanvasActionHref(action, studyMode)}
              className={`block rounded-full px-3 py-1.5 text-center text-sm break-words focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
                primary
                  ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                  : "border border-[var(--border)] hover:border-[var(--accent)]"
              }`}
            >
              {action.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
