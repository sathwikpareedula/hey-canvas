"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { NotificationListPanel } from "@/components/notifications/NotificationListPanel";
import { useNotifications } from "@/contexts/NotificationContext";

export function NotificationBell() {
  const { notifications, unreadCount, markRead, dismiss, markAllRead, loading, error, refresh } =
    useNotifications();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-md border border-[var(--border)] px-2 py-1 text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls="notification-popover"
        aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
      >
        Inbox
        {unreadCount > 0 ? (
          <span
            className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--accent)] px-1 text-[10px] text-[var(--accent-fg)]"
            aria-hidden
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40"
            aria-label="Close notifications"
            onClick={() => setOpen(false)}
          />
          <div
            ref={panelRef}
            id="notification-popover"
            role="dialog"
            aria-label="Notifications"
            className="absolute right-0 z-50 mt-2 w-[min(100vw-2rem,22rem)] rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-lg"
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
              <span className="text-sm font-medium">Notifications</span>
              <div className="flex items-center gap-2 text-xs">
                <button type="button" className="text-[var(--muted)] underline" onClick={() => refresh()}>
                  Refresh
                </button>
                <button type="button" className="text-[var(--muted)] underline" onClick={() => markAllRead()}>
                  Mark all read
                </button>
              </div>
            </div>
            <NotificationListPanel
              compact
              notifications={notifications}
              loading={loading}
              error={error}
              onRead={(id) => {
                void markRead(id);
              }}
              onDismiss={(id) => {
                void dismiss(id);
              }}
            />
            <div className="border-t border-[var(--border)] px-3 py-2 text-center">
              <Link
                href="/notifications"
                className="text-xs text-[var(--accent)] underline"
                onClick={() => setOpen(false)}
              >
                View all notifications
              </Link>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
