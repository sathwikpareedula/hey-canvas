"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { useSourceDrawer } from "@/contexts/SourceDrawerContext";
import {
  evidenceSourceKindLabel,
  inferEvidenceSourceKind,
} from "@/lib/evidence/source-kind";

function ProvenanceField({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs text-[var(--muted)]">{label}</dt>
      <dd className="break-words text-[var(--foreground)]">{value}</dd>
    </div>
  );
}

function formatUnit(provenance: {
  unit?: { label: string; page?: number; slide?: number; section?: string };
}) {
  const u = provenance.unit;
  if (!u) return null;
  const parts = [u.label];
  if (u.section) parts.push(u.section);
  if (u.page != null) parts.push(`Page ${u.page}`);
  if (u.slide != null) parts.push(`Slide ${u.slide}`);
  return parts.join(" · ");
}

export function SourceDrawer() {
  const { open, provenance, closeSource } = useSourceDrawer();
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) closeSource();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, closeSource]);

  if (!open || !provenance) return null;

  const title =
    provenance.documentTitle ??
    provenance.fileName ??
    provenance.moduleItemTitle ??
    "Source";
  const kind = inferEvidenceSourceKind(provenance);
  const location = formatUnit(provenance);

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-black/40"
        aria-label="Close source panel"
        onClick={closeSource}
      />
      <aside
        ref={panelRef}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-xl pb-[env(safe-area-inset-bottom)]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-drawer-title"
      >
        <header className="flex items-start justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <div className="min-w-0 pr-2">
            <div className="mb-1 flex flex-wrap gap-1">
              <span className="inline-block rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
                {evidenceSourceKindLabel(kind)}
              </span>
              {provenance.isStale ? (
                <span className="inline-block rounded-full bg-[var(--warn-bg)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--warn-text)]">
                  Stale evidence
                </span>
              ) : null}
            </div>
            <h2 id="source-drawer-title" className="text-sm font-semibold break-words">
              {title}
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={closeSource}
            className="shrink-0 min-h-9 rounded-md px-3 py-1 text-sm text-[var(--muted)] hover:bg-[var(--surface-muted)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            Close
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-4 text-sm">
          <dl className="space-y-3">
            <ProvenanceField label="Course" value={provenance.courseName} />
            <ProvenanceField label="Module" value={provenance.moduleName} />
            <ProvenanceField label="Module item" value={provenance.moduleItemTitle} />
            <ProvenanceField label="Document" value={provenance.documentTitle} />
            <ProvenanceField label="File name" value={provenance.fileName} />
            <ProvenanceField label="Location" value={location} />
          </dl>
          {provenance.documentId ? (
            <Link
              href={`/materials/${provenance.documentId}`}
              className="mt-4 inline-block text-sm text-[var(--accent)] underline"
            >
              View material in library
            </Link>
          ) : null}
          {provenance.excerpt ? (
            <div className="mt-6 rounded-lg bg-[var(--surface-muted)] p-3 text-xs leading-relaxed text-[var(--muted)] break-words">
              <p className="mb-1 font-medium text-[var(--foreground)]">Excerpt</p>
              {provenance.excerpt}
            </div>
          ) : (
            <p className="mt-6 text-xs text-[var(--muted)]">
              Full document preview will load from the backend provenance API when available.
              Citations never include local file paths or signed URLs in the browser.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
