"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { STUDY_MODE_OPTIONS, parseStudyMode, type StudyMode } from "@/lib/domain/study-mode";
export function StudyModeSelector() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const active = parseStudyMode(searchParams.get("studyMode"));
  const activeMeta = STUDY_MODE_OPTIONS.find((m) => m.id === active);

  const setMode = (mode: StudyMode | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (mode) params.set("studyMode", mode);
    else params.delete("studyMode");
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-medium uppercase tracking-wide text-[var(--muted)]">Study mode</span>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Study mode">
          <button
            type="button"
            aria-pressed={!active}
            onClick={() => setMode(null)}
            className={`min-h-9 rounded-full px-3 py-1 ${
              !active
                ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                : "border border-[var(--border)]"
            } focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]`}
          >
            General
          </button>
          {STUDY_MODE_OPTIONS.map((m) => (
            <button
              key={m.id}
              type="button"
              aria-pressed={active === m.id}
              title={m.description}
              onClick={() => setMode(m.id)}
              className={`min-h-9 rounded-full px-3 py-1 ${
                active === m.id
                  ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                  : "border border-[var(--border)]"
              } focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      {activeMeta ? (
        <p className="text-xs text-[var(--muted)]" id="study-mode-hint">
          {activeMeta.description}. Exam prep maps to backend{" "}
          <code className="text-[0.85em]">exam_prep</code> when HTTP mode is enabled.
        </p>
      ) : (
        <p className="text-xs text-[var(--muted)]" id="study-mode-hint">
          Optional tone for Hey Canvas. Learn, Review, Practice, and Exam prep adjust how
          questions are framed — not separate backend assistants.
        </p>
      )}
    </div>
  );
}
