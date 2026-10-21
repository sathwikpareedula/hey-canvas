"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  probeBackendConnection,
  type BackendConnectionState,
} from "@/lib/api/backend-probe";
import { getApiMode } from "@/lib/api";

interface BackendStatusContextValue {
  mode: "mock" | "http";
  connection: BackendConnectionState;
  refresh: () => void;
  checking: boolean;
}

const BackendStatusContext = createContext<BackendStatusContextValue | null>(null);

export function BackendStatusProvider({ children }: { children: React.ReactNode }) {
  const mode = getApiMode();
  const [connection, setConnection] = useState<BackendConnectionState>(
    mode === "mock" ? "mock" : "unavailable",
  );
  const [checking, setChecking] = useState(mode === "http");

  const refresh = useCallback(() => {
    if (mode === "mock") {
      setConnection("mock");
      setChecking(false);
      return;
    }
    setChecking(true);
    probeBackendConnection()
      .then(setConnection)
      .finally(() => setChecking(false));
  }, [mode]);

  useEffect(() => {
    if (mode === "mock") return;
    let active = true;
    probeBackendConnection()
      .then((state) => {
        if (active) setConnection(state);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, [mode]);

  const value = useMemo(
    () => ({ mode, connection, refresh, checking }),
    [mode, connection, refresh, checking],
  );

  return (
    <BackendStatusContext.Provider value={value}>{children}</BackendStatusContext.Provider>
  );
}

export function useBackendStatus() {
  const ctx = useContext(BackendStatusContext);
  if (!ctx) throw new Error("useBackendStatus must be used within BackendStatusProvider");
  return ctx;
}
