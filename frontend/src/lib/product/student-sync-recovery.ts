import type { SyncRun, SyncRunStatus } from "@/lib/domain/types";

export function syncStatusRecoveryHint(run: SyncRun | null): string | null {
  if (!run) {
    return "After Canvas sync completes on your computer, refresh status here or revisit Settings.";
  }
  if (run.status === "failed" || run.status === "interrupted") {
    return "Check Canvas token and network on your computer, run sync again, then refresh status below.";
  }
  if (run.status === "partially_succeeded") {
    return "Some courses or materials may be missing. Re-run sync on your computer if lists look incomplete.";
  }
  return null;
}

export function syncStatusIsUnhealthy(status: SyncRunStatus): boolean {
  return status === "failed" || status === "interrupted" || status === "partially_succeeded";
}
