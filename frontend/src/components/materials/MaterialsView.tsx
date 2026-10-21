"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { MaterialSearchResult } from "@/components/materials/MaterialSearchResult";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { Course, DocumentSearchResult, DocumentType } from "@/lib/domain/types";

export function MaterialsView() {
  const api = useAcademicApi();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [courses, setCourses] = useState<Course[]>([]);
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [courseId, setCourseId] = useState(searchParams.get("course") ?? "");
  const [documentType, setDocumentType] = useState<DocumentType | "">(
    (searchParams.get("type") as DocumentType) ?? "",
  );
  const [results, setResults] = useState<DocumentSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const syncUrl = useCallback(
    (next: { q?: string; course?: string; type?: string }) => {
      const params = new URLSearchParams();
      const q = next.q ?? query;
      const c = next.course ?? courseId;
      const t = next.type ?? documentType;
      if (q) params.set("q", q);
      if (c) params.set("course", c);
      if (t) params.set("type", t);
      const qs = params.toString();
      router.replace(qs ? `/materials?${qs}` : "/materials");
    },
    [router, query, courseId, documentType],
  );

  useEffect(() => {
    api.getCourses().then(setCourses).catch((err) => setError(err));
  }, [api]);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      setError(null);
      api
        .searchDocuments({
          query,
          courseId: courseId || undefined,
          documentType: documentType || undefined,
        })
        .then((r) => {
          setResults(r);
          setActiveIndex(0);
        })
        .catch((err) => setError(err))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [api, query, courseId, documentType]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          if (e.key === "ArrowDown") setActiveIndex((i) => Math.min(i + 1, results.length - 1));
          if (e.key === "ArrowUp") setActiveIndex((i) => Math.max(i - 1, 0));
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [results.length]);

  const hasQuery = query.trim().length > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <label className="block text-sm font-medium">
          Search professor materials
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              syncUrl({ q: e.target.value });
            }}
            placeholder="Search professor materials..."
            className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
          />
        </label>
        <div className="flex flex-wrap gap-3 text-sm">
          <label>
            <span className="text-[var(--muted)]">Course </span>
            <select
              value={courseId}
              onChange={(e) => {
                setCourseId(e.target.value);
                syncUrl({ course: e.target.value });
              }}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1"
            >
              <option value="">All</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-[var(--muted)]">Type </span>
            <select
              value={documentType}
              onChange={(e) => {
                setDocumentType(e.target.value as DocumentType | "");
                syncUrl({ type: e.target.value });
              }}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1"
            >
              <option value="">All</option>
              <option value="pdf">PDF</option>
              <option value="slides">Slides</option>
              <option value="notes">Notes</option>
              <option value="assignment">Assignment</option>
              <option value="other">Other</option>
            </select>
          </label>
        </div>
      </div>

      {error ? <ApiErrorPanel error={error} onRetry={() => syncUrl({})} /> : null}
      {loading ? <PageSkeleton /> : null}

      {!loading && !error && (
        <>
          <p className="text-sm text-[var(--muted)]">
            {results.length} result{results.length === 1 ? "" : "s"}
            {hasQuery ? ` for “${query.trim()}”` : " (browse indexed documents)"}
          </p>
          {!hasQuery && results.length > 0 ? (
            <p className="text-xs text-[var(--muted)]">
              Tip: try searching “kinematics” or “lecture”.
            </p>
          ) : null}
          {!hasQuery && results.length === 0 ? (
            <EmptyState
              title="No materials indexed"
              description="Documents appear here after backend sync and parsing. This is not a crash — the catalog may simply be empty."
            />
          ) : null}
          {hasQuery && results.length === 0 ? (
            <EmptyState title="No results" description="Try another query or filter." />
          ) : null}
          <div className="space-y-3">
            {results.map((r, index) => (
              <div
                key={`${r.documentId}-${r.unit.label}`}
                className={index === activeIndex ? "ring-2 ring-[var(--accent)] rounded-xl" : ""}
              >
                <MaterialSearchResult result={r} query={query} active={index === activeIndex} />
              </div>
            ))}
          </div>
          {results[activeIndex] ? (
            <p className="text-xs text-[var(--muted)]">
              Press ↑↓ while focused in search to highlight results.{" "}
              <Link href={`/materials/${results[activeIndex].documentId}`} className="underline">
                Open highlighted
              </Link>
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
