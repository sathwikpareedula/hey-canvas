"use client";

import { NotificationListPanel } from "@/components/notifications/NotificationListPanel";
import { useNotifications } from "@/contexts/NotificationContext";

export function NotificationsPageView() {
  const { notifications, loading, error, markRead, dismiss, refresh, markAllRead } =
    useNotifications();

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Notifications</h1>
          <p className="text-sm text-[var(--muted)]">
            Derived from your local Canvas sync and change history — not live push alerts.
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <button type="button" className="underline" onClick={() => refresh()}>
            Refresh
          </button>
          <button type="button" className="underline" onClick={() => void markAllRead()}>
            Mark all read
          </button>
        </div>
      </header>
      <section className="rounded-xl border border-[var(--border)]">
        <NotificationListPanel
          notifications={notifications}
          loading={loading}
          error={error}
          onRead={(id) => void markRead(id)}
          onDismiss={(id) => void dismiss(id)}
        />
      </section>
    </div>
  );
}
