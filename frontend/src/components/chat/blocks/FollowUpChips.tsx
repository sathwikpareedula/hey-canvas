export function FollowUpChips({
  items,
  onSelect,
}: {
  items?: string[];
  onSelect?: (prompt: string) => void;
}) {
  if (!items?.length || !onSelect) return null;
  return (
    <ul className="flex flex-wrap gap-2 pt-1" aria-label="Suggested follow-ups">
      {items.map((f) => (
        <li key={f}>
          <button
            type="button"
            onClick={() => onSelect(f)}
            className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            {f}
          </button>
        </li>
      ))}
    </ul>
  );
}
