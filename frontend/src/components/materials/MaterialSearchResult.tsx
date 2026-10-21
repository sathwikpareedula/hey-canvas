"use client";

import Link from "next/link";
import { DocumentStatusBadge } from "@/components/materials/DocumentStatusBadge";
import { SourceCitationButton } from "@/components/sources/SourceCitation";
import type { DocumentSearchResult } from "@/lib/domain/types";
import { HighlightedText } from "@/lib/utils/highlight";

export function MaterialSearchResult({
  result,
  query = "",
  active,
}: {
  result: DocumentSearchResult;
  query?: string;
  active?: boolean;
}) {
  return (
    <article
      className={`rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 ${
        active ? "border-[var(--accent)]" : ""
      }`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link href={`/materials/${result.documentId}`} className="text-sm font-medium hover:underline break-words">
            <HighlightedText text={result.title} query={query} />
          </Link>
          <p className="text-xs text-[var(--muted)] mt-1">
            <span className="font-medium text-[var(--foreground)]">Document</span>
            {" · "}
            {result.courseName}
            {" · "}
            <span>Unit: {result.unit.label}</span>
            {result.provenance.moduleName ? (
              <>
                {" · "}
                <span>Module: {result.provenance.moduleName}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs text-[var(--muted)]">
            {result.documentType}
          </span>
          <DocumentStatusBadge isStale={result.isStale} ingestionState="searchable" />
        </div>
      </header>
      <p className="mt-2 text-sm italic text-[var(--muted)] break-words">
        <HighlightedText text={result.snippet} query={query} />
      </p>
      <div className="mt-3">
        <SourceCitationButton provenance={result.provenance} />
      </div>
    </article>
  );
}
