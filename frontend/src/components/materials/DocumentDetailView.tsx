"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SourceCitationButton } from "@/components/sources/SourceCitation";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { DocumentStatusBadge } from "@/components/materials/DocumentStatusBadge";
import { HeyCanvasActionLinks } from "@/components/ui/HeyCanvasActionLinks";
import { materialHeyCanvasActions } from "@/lib/navigation/hey-canvas-actions";
import { ContextualStudyActions } from "@/components/study/ContextualStudyActions";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { buildStudyWorkspaceUrl } from "@/lib/navigation/study-links";
import type { DocumentDetail } from "@/lib/domain/types";

export function DocumentDetailView({ documentId }: { documentId: string }) {
  const api = useAcademicApi();
  const [doc, setDoc] = useState<DocumentDetail | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    api
      .getDocument(documentId)
      .then((d) => {
        if (!active) return;
        setDoc(d);
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
  }, [api, documentId]);

  if (loading) return <PageSkeleton />;
  if (error) return <ApiErrorPanel error={error} />;
  if (doc === null) {
    return (
      <EmptyState
        title="Material not found"
        action={<Link href="/materials" className="text-sm underline">Back to materials</Link>}
      />
    );
  }
  if (!doc) return null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h2 className="text-xl font-semibold break-words">{doc.title}</h2>
        <p className="text-sm text-[var(--muted)]">
          {doc.courseName} · {doc.documentType} · {doc.ingestionState}
        </p>
        <div className="mt-2">
          <DocumentStatusBadge
            ingestionState={doc.ingestionState}
            backendStatus={doc.backendStatus}
            needsOcr={doc.needsOcr}
            isStale={doc.isStale}
          />
        </div>
      </header>

      <SourceCitationButton provenance={doc.provenance} />

      <section>
        <h3 className="text-sm font-semibold">Preview (sample parsed text)</h3>
        <pre className="mt-2 whitespace-pre-wrap rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm font-sans">
          {doc.previewPlainText}
        </pre>
      </section>

      {doc.units?.length ? (
        <section>
          <h3 className="text-sm font-semibold">Structure</h3>
          <ul className="mt-2 flex flex-col gap-2 text-sm">
            {doc.units.map((u) => (
              <li
                key={u.label}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border)] px-3 py-2"
              >
                <span className="break-words">{u.label}</span>
                <Link
                  href={buildHeyCanvasUrl({
                    courseId: doc.courseId,
                    documentId: doc.id,
                    prompt: `Explain ${u.label} in “${doc.title}”.`,
                  })}
                  className="shrink-0 text-xs text-[var(--accent)] underline"
                >
                  Ask Hey Canvas
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Study this material</h3>
        <ContextualStudyActions
          layout="chips"
          courseId={doc.courseId}
          courseName={doc.courseName}
          documentId={doc.id}
          materialTitle={doc.title}
        />
        <Link
          href={buildStudyWorkspaceUrl({
            courseId: doc.courseId,
            documentId: doc.id,
            studyMode: "learn",
            practiceTopic: doc.title,
          })}
          className="text-sm text-[var(--accent)] underline"
        >
          Open study workspace for this material
        </Link>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Study with Hey Canvas</h3>
        <HeyCanvasActionLinks
          primaryId="explain"
          actions={materialHeyCanvasActions(doc.title, {
            documentId: doc.id,
            courseId: doc.courseId,
          })}
        />
        <Link
          href={`/materials?q=${encodeURIComponent(doc.title.split(" ")[0] ?? "")}&course=${doc.courseId}`}
          className="inline-block text-sm text-[var(--accent)] underline"
        >
          Search related materials in this course
        </Link>
      </section>

      {doc.technical ? (
        <details className="rounded-xl border border-[var(--border)] p-3 text-xs text-[var(--muted)]">
          <summary className="cursor-pointer font-medium text-[var(--foreground)]">
            Technical details
          </summary>
          <p className="mt-2">Parser: {doc.technical.parserVersion ?? "—"}</p>
          <p>Content SHA-256 (sample): {doc.technical.contentSha256 ?? "—"}</p>
        </details>
      ) : null}
    </div>
  );
}
