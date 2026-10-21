"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { AcademicApiError } from "@/lib/api/errors";
import type { AppNotification } from "@/lib/domain/types";

interface NotificationContextValue {
  notifications: AppNotification[];
  unreadCount: number;
  loading: boolean;
  error: string | null;
  markRead: (id: string) => Promise<void>;
  dismiss: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  refresh: () => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const api = useAcademicApi();
  const { mode, connection } = useBackendStatus();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getNotifications()
      .then((items) => {
        setNotifications(items.filter((n) => !n.dismissed));
        setLoading(false);
      })
      .catch((err) => {
        const message =
          err instanceof AcademicApiError
            ? err.message
            : mode === "http" && connection !== "connected"
              ? "Connect to the academic API to load notifications."
              : "Could not load notifications.";
        setError(message);
        setNotifications([]);
        setLoading(false);
      });
  }, [api, mode, connection]);

  useEffect(() => {
    queueMicrotask(() => refresh());
  }, [refresh]);

  const markRead = useCallback(
    async (id: string) => {
      try {
        const updated = await api.markNotificationRead(id);
        setNotifications((list) =>
          list.map((n) => (n.id === id ? { ...n, ...updated, dismissed: n.dismissed } : n)),
        );
      } catch {
        setNotifications((list) => list.map((n) => (n.id === id ? { ...n, read: true } : n)));
      }
    },
    [api],
  );

  const dismiss = useCallback(
    async (id: string) => {
      try {
        await api.dismissNotification(id);
      } catch {
        /* still remove locally */
      }
      setNotifications((list) => list.filter((n) => n.id !== id));
    },
    [api],
  );

  const markAllRead = useCallback(async () => {
    const unread = notifications.filter((n) => !n.read);
    await Promise.all(unread.map((n) => markRead(n.id)));
  }, [notifications, markRead]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const value = useMemo(
    () => ({
      notifications,
      unreadCount,
      loading,
      error,
      markRead,
      dismiss,
      markAllRead,
      refresh,
    }),
    [notifications, unreadCount, loading, error, markRead, dismiss, markAllRead, refresh],
  );

  return (
    <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationProvider");
  return ctx;
}
