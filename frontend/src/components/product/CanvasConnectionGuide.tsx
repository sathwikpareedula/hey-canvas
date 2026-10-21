export function CanvasConnectionGuide({ compact }: { compact?: boolean }) {
  const body = (
    <>
      <p className="font-medium text-[var(--foreground)]">
        Canvas connects on your computer — not in this browser
      </p>
      <ol className="list-decimal space-y-1 pl-4">
        <li>Start the Hey Canvas service on this machine (launcher or your usual command).</li>
        <li>
          Add a read-only Canvas API token in that service&apos;s configuration file — never paste
          tokens into this website or browser storage.
        </li>
        <li>Run an initial Canvas sync from the service; courses appear here after sync succeeds.</li>
      </ol>
      <p>
        If sync fails, fix credentials on the computer and sync again. This app only shows sync
        status and course data from your local service.
      </p>
    </>
  );

  if (compact) {
    return <div className="space-y-2 text-xs text-[var(--muted)]">{body}</div>;
  }

  return (
    <div className="space-y-2 rounded-lg bg-[var(--surface-muted)] px-3 py-3 text-xs text-[var(--muted)]">
      {body}
    </div>
  );
}
