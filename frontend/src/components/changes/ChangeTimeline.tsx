import type { ChangeEvent } from "@/lib/domain/types";
import {
  formatChangeValue,
  humanizeChangeFieldName,
} from "@/lib/utils/chicago-date";
import { formatRelativeTime } from "@/lib/utils/date";

function eventLabel(event: ChangeEvent): string {
  return event.eventType.replaceAll("_", " ");
}

export function ChangeTimeline({ events }: { events: ChangeEvent[] }) {
  if (!events.length) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-center text-sm text-[var(--muted)]">
        No recorded changes in this view. Changes appear after backend sync detects updates in
        local Canvas data.
      </p>
    );
  }

  return (
    <ol className="relative space-y-0 border-l border-[var(--border)] pl-4">
      {events.map((event) => (
        <li key={event.id} className="relative pb-6 last:pb-0">
          <span
            className="absolute -left-[0.4375rem] top-1.5 h-2.5 w-2.5 rounded-full bg-[var(--accent)]"
            aria-hidden
          />
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm font-medium break-words text-[var(--foreground)]">
                {event.entityLabel}
              </p>
              <time className="text-xs text-[var(--muted)]" dateTime={event.observedAt}>
                {formatRelativeTime(event.observedAt)}
              </time>
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {event.courseName ?? "—"} · {event.entityType} · {eventLabel(event)}
            </p>
            {event.fieldName && (event.oldValue || event.newValue) ? (
              <p className="mt-2 text-xs text-[var(--foreground)]">
                <span className="font-medium text-[var(--muted)]">
                  {humanizeChangeFieldName(event.fieldName)} changed:{" "}
                </span>
                {event.oldValue ? <span>{formatChangeValue(event.oldValue)}</span> : null}
                {event.oldValue && event.newValue ? (
                  <span className="text-[var(--muted)]"> → </span>
                ) : null}
                {event.newValue ? <span>{formatChangeValue(event.newValue)}</span> : null}
              </p>
            ) : event.newValue ? (
              <p className="mt-2 text-xs text-[var(--foreground)]">
                {formatChangeValue(event.newValue)}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
