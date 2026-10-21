import type { DocumentIngestionState } from "@/lib/domain/types";
import { documentUserStatus } from "@/lib/materials/document-presentation";

export function DocumentStatusBadge({
  ingestionState,
  backendStatus,
  needsOcr,
  isStale,
}: {
  ingestionState?: DocumentIngestionState;
  backendStatus?: string;
  needsOcr?: boolean;
  isStale?: boolean;
}) {
  const status = documentUserStatus({
    ingestionState,
    backendStatus,
    needsOcr,
    isStale,
  });
  if (!status) return null;
  const toneClass =
    status.tone === "warn"
      ? "bg-[var(--warn-bg)] text-[var(--warn-text)]"
      : status.tone === "danger"
        ? "bg-[var(--danger-bg)] text-[var(--danger-text)]"
        : status.tone === "ok"
          ? "bg-emerald-500/15 text-emerald-900 dark:text-emerald-100"
          : "bg-[var(--surface-muted)] text-[var(--muted)]";
  return (
    <span
      className={`inline-flex max-w-full flex-col gap-0.5 rounded-lg px-2 py-1 text-xs ${toneClass}`}
      aria-label="Material status"
      title={status.description}
    >
      <span className="font-medium">{status.label}</span>
    </span>
  );
}
