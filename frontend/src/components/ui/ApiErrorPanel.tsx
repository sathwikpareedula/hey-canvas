import { presentAcademicError } from "@/lib/api/error-presentation";

export function ApiErrorPanel({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const presented = presentAcademicError(error);

  const informational =
    presented.kind === "not_implemented" ||
    presented.title === "Action needed" ||
    presented.title === "No saved session";

  return (
    <div
      className={`rounded-xl border px-4 py-3 text-sm ${
        informational
          ? "border-[var(--border)] bg-[var(--surface-muted)] text-[var(--foreground)]"
          : "border-[var(--danger-border)] bg-[var(--danger-bg)] text-[var(--danger-text)]"
      }`}
      role={informational ? "status" : "alert"}
    >
      <p className="font-medium">{presented.title}</p>
      <p className="mt-1 text-[0.9em] opacity-90">{presented.message}</p>
      {presented.retryable && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 font-medium underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
