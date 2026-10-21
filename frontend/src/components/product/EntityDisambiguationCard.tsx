"use client";

import type { DisambiguationCandidate } from "@/lib/domain/product-settings";

export function EntityDisambiguationCard({
  title,
  candidates,
  onPick,
}: {
  title: string;
  candidates: DisambiguationCandidate[];
  onPick: (candidate: DisambiguationCandidate) => void;
}) {
  if (!candidates.length) return null;
  return (
    <div
      className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-3 text-sm"
      role="group"
      aria-label={title}
    >
      <p className="font-medium text-[var(--foreground)]">{title}</p>
      <ul className="mt-2 space-y-1">
        {candidates.map((c) => (
          <li key={`${c.kind}-${c.id}`}>
            <button
              type="button"
              onClick={() => onPick(c)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            >
              <span className="block truncate font-medium">{c.title}</span>
              {c.subtitle ? (
                <span className="block truncate text-xs text-[var(--muted)]">{c.subtitle}</span>
              ) : c.kind !== "course" ? (
                <span className="block text-xs text-[var(--muted)] capitalize">{c.kind}</span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
