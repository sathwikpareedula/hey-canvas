"use client";

import { useSourceDrawer } from "@/contexts/SourceDrawerContext";
import {
  evidenceSourceKindLabel,
  inferEvidenceSourceKind,
} from "@/lib/evidence/source-kind";
import type { AssistantSource, Provenance } from "@/lib/domain/types";

function provenanceTitle(p: Provenance): string {
  return p.documentTitle ?? p.fileName ?? p.moduleItemTitle ?? "Source";
}

function provenanceSubtitle(p: Provenance): string {
  const parts = [p.courseName];
  if (p.moduleName) parts.push(p.moduleName);
  if (p.unit?.label) parts.push(p.unit.label);
  if (p.unit?.page != null) parts.push(`p. ${p.unit.page}`);
  if (p.unit?.slide != null) parts.push(`slide ${p.unit.slide}`);
  return parts.join(" · ");
}

export function SourceCitationList({ sources }: { sources: AssistantSource[] }) {
  const seen = new Set<string>();
  const uniqueSources = sources.filter((source) => {
    const provenance = source.provenance;
    const key = provenance.documentId
      ? `document:${provenance.courseId}:${provenance.documentId}`
      : `source:${provenance.courseId}:${source.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (!uniqueSources.length) return null;
  return (
    <details className="group mt-3 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)]/30 p-2 text-xs transition">
      <summary className="flex cursor-pointer select-none items-center justify-between px-1 py-0.5 font-medium text-[var(--muted)] hover:text-[var(--foreground)]">
        <span className="flex items-center gap-1.5">
          <span>📚 Sources</span>
          <span className="rounded-full border border-[var(--border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--foreground)]">
            {uniqueSources.length}
          </span>
        </span>
        <span className="text-[10px] text-[var(--muted)] transition-transform group-open:rotate-180">
          ▼
        </span>
      </summary>
      <ul className="mt-2 space-y-1 border-t border-[var(--border)] pt-2">
        {uniqueSources.map((s) => (
          <li key={s.id}>
            <SourceCitationButton provenance={s.provenance} />
          </li>
        ))}
      </ul>
    </details>
  );
}

export function SourceCitationButton({ provenance }: { provenance: Provenance }) {
  const { openSource } = useSourceDrawer();
  const kind = inferEvidenceSourceKind(provenance);
  const hasMaterialRecord = Boolean(provenance.documentId);
  return (
    <button
      type="button"
      onClick={() => openSource(provenance)}
      className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left transition hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
    >
      <span className="mb-1 flex flex-wrap gap-1">
        <span className="inline-block rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
          {evidenceSourceKindLabel(kind)}
        </span>
        {provenance.isStale ? (
          <span className="inline-block rounded-full bg-[var(--warn-bg)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--warn-text)]">
            Stale
          </span>
        ) : null}
      </span>
      <span className="block text-sm font-medium break-words text-[var(--foreground)]">
        {provenanceTitle(provenance)}
      </span>
      <span className="block text-xs break-words text-[var(--muted)]">{provenanceSubtitle(provenance)}</span>
      {hasMaterialRecord ? (
        <span className="mt-1 block text-xs text-[var(--accent)]">Open material record</span>
      ) : null}
    </button>
  );
}
