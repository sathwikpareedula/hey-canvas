"use client";

import { useEffect, useState } from "react";
import { fetchJson, postJson } from "@/lib/api/http/fetch-json";

export interface StorageSummaryData {
  total_storage_bytes: number;
  database_bytes: number;
  cached_files_bytes: number;
  cached_files_count: number;
  indexed_documents_count: number;
  indexed_units_count: number;
  metadata_only_files_count: number;
  needs_ocr_files_count: number;
  failed_documents_count: number;
  orphaned_files_count: number;
  orphaned_files_bytes: number;
  temp_files_count: number;
  temp_files_bytes: number;
  last_sync_timestamp: string | null;
  last_sync_status: string | null;
  storage_root: string;
  database_path: string;
}

export interface StorageCleanupResultData {
  ok: boolean;
  message: string;
  bytes_freed: number;
  files_removed: number;
  is_dry_run: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export function StorageSettingsPanel() {
  const [data, setData] = useState<StorageSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cleaning, setCleaning] = useState(false);
  const [cleanupMessage, setCleanupMessage] = useState<string | null>(null);

  const refreshSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const summary = await fetchJson<StorageSummaryData>("/api/storage/summary");
      setData(summary);
    } catch {
      setError("Unable to load storage metrics. Is the local backend running?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    fetchJson<StorageSummaryData>("/api/storage/summary")
      .then((summary) => {
        if (active) {
          setData(summary);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setError("Unable to load storage metrics. Is the local backend running?");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCleanup = async () => {
    if (!window.confirm("Clean temporary download (.part) files? Downloaded materials will be preserved.")) {
      return;
    }
    setCleaning(true);
    setCleanupMessage(null);
    try {
      const result = await postJson<StorageCleanupResultData>("/api/storage/cleanup", {
        confirm: true,
        remove_temp_files: true,
        remove_orphans: false,
      });
      setCleanupMessage(result.message);
      await refreshSummary();
    } catch {
      setCleanupMessage("Failed to execute storage cleanup.");
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold">Local Storage &amp; Cache</h2>
          <p className="text-xs text-[var(--muted)]">
            Inspection of local SQLite database, downloaded course files, and indexed text units.
          </p>
        </div>
        <button
          type="button"
          onClick={refreshSummary}
          disabled={loading}
          className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && <p className="text-xs text-red-500">{error}</p>}
      {cleanupMessage && <p className="text-xs text-emerald-600">{cleanupMessage}</p>}

      {loading && !data ? (
        <p className="text-xs text-[var(--muted)]">Loading storage metrics…</p>
      ) : data ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-2.5">
              <span className="block text-[10px] uppercase tracking-wider text-[var(--muted)]">Total Used</span>
              <span className="text-base font-bold text-[var(--foreground)]">{formatBytes(data.total_storage_bytes)}</span>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-2.5">
              <span className="block text-[10px] uppercase tracking-wider text-[var(--muted)]">Database</span>
              <span className="text-base font-bold text-[var(--foreground)]">{formatBytes(data.database_bytes)}</span>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-2.5">
              <span className="block text-[10px] uppercase tracking-wider text-[var(--muted)]">Cached Files</span>
              <span className="text-base font-bold text-[var(--foreground)]">{formatBytes(data.cached_files_bytes)}</span>
              <span className="block text-[10px] text-[var(--muted)]">{data.cached_files_count} files</span>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-2.5">
              <span className="block text-[10px] uppercase tracking-wider text-[var(--muted)]">Indexed Units</span>
              <span className="text-base font-bold text-[var(--foreground)]">{data.indexed_units_count}</span>
              <span className="block text-[10px] text-[var(--muted)]">{data.indexed_documents_count} parsed docs</span>
            </div>
          </div>

          <div className="rounded-lg border border-[var(--border)] p-3 text-xs space-y-1.5">
            <div className="flex justify-between py-1 border-b border-[var(--border)]">
              <span className="text-[var(--muted)]">Metadata-only files (not yet downloaded):</span>
              <span className="font-medium">{data.metadata_only_files_count}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[var(--border)]">
              <span className="text-[var(--muted)]">Scanned documents needing OCR:</span>
              <span className="font-medium text-amber-600">{data.needs_ocr_files_count}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[var(--border)]">
              <span className="text-[var(--muted)]">Temporary (.part) files:</span>
              <span className="font-medium">{data.temp_files_count} ({formatBytes(data.temp_files_bytes)})</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[var(--border)]">
              <span className="text-[var(--muted)]">Last successful sync:</span>
              <span className="font-medium">{data.last_sync_timestamp ? new Date(data.last_sync_timestamp).toLocaleString() : "None"}</span>
            </div>
            <div className="pt-1 text-[11px] text-[var(--muted)] break-all">
              <span>Data root: </span><code className="rounded bg-[var(--surface-muted)] px-1">{data.storage_root}</code>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCleanup}
              disabled={cleaning || data.temp_files_count === 0}
              className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium disabled:opacity-40"
            >
              {cleaning ? "Cleaning…" : `Clean Temp Files (${data.temp_files_count})`}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
