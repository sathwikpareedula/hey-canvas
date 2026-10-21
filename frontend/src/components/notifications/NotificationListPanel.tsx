"use client";

import Link from "next/link";
import { notificationTypeLabel, severityTone } from "@/lib/notifications/presentation";
import type { AppNotification } from "@/lib/domain/types";
import { formatRelativeTime } from "@/lib/utils/date";

export function NotificationListPanel({
  notifications,
  loading,
  error,
  onRead,
  onDismiss,
  compact = false,
}: {
  notifications: AppNotification[];
  loading?: boolean;
  error?: string | null;
  onRead: (id: string) => void;
  onDismiss: (id: string) => void;
  compact?: boolean;
}) {
  if (loading) {
    return (
      <p className="px-3 py-6 text-center text-sm text-[var(--muted)]" role="status">
        Loading notifications…
      </p>
    );
  }
  if (error) {
    return (
      <p className="px-3 py-6 text-center text-sm text-[var(--danger-text)]" role="alert">
        {error}
      </p>
    );
  }
  if (notifications.length === 0) {
    return (
      <p className="px-3 py-6 text-center text-sm text-[var(--muted)]">
        No active notifications. Assignment deadlines and course changes from your local sync will
        appear here.
      </p>
    );
  }

  return (
    <ul className={compact ? "max-h-80 overflow-y-auto" : "space-y-2"}>
      {notifications.map((n) => (
        <li
          key={n.id}
          className={`border-b border-[var(--border)] last:border-b-0 border-l-2 pl-2 ${severityTone(
            n.severity,
          )} ${n.read ? "opacity-75" : "bg-[var(--surface-muted)]/40"}`}
        >
          <div className="flex flex-wrap items-start justify-between gap-2 px-2 py-2">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
                {notificationTypeLabel(n.notificationType)}
              </p>
              {n.href ? (
                <Link
                  href={n.href}
                  onClick={() => onRead(n.id)}
                  className="block text-sm font-medium hover:underline break-words"
                >
                  {n.title}
                </Link>
              ) : (
                <p className="text-sm font-medium break-words">{n.title}</p>
              )}
              <p className="text-xs text-[var(--muted)] break-words">{n.body}</p>
              <p className="mt-1 text-[10px] text-[var(--muted)]">
                {formatRelativeTime(n.createdAt)}
              </p>
            </div>
            <div className="flex shrink-0 flex-col gap-1">
              {!n.read ? (
                <button
                  type="button"
                  className="text-[10px] underline"
                  onClick={() => onRead(n.id)}
                >
                  Mark read
                </button>
              ) : null}
              <button
                type="button"
                className="text-[10px] text-[var(--muted)] underline"
                onClick={() => onDismiss(n.id)}
              >
                Dismiss
              </button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
