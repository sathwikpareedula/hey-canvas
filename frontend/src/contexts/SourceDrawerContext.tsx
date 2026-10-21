"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { Provenance } from "@/lib/domain/types";

interface SourceDrawerContextValue {
  open: boolean;
  provenance: Provenance | null;
  openSource: (p: Provenance) => void;
  closeSource: () => void;
}

const SourceDrawerContext = createContext<SourceDrawerContextValue | null>(null);

export function SourceDrawerProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [provenance, setProvenance] = useState<Provenance | null>(null);

  const openSource = useCallback((p: Provenance) => {
    setProvenance(p);
    setOpen(true);
  }, []);

  const closeSource = useCallback(() => {
    setOpen(false);
  }, []);

  const value = useMemo(
    () => ({ open, provenance, openSource, closeSource }),
    [open, provenance, openSource, closeSource],
  );

  return (
    <SourceDrawerContext.Provider value={value}>
      {children}
    </SourceDrawerContext.Provider>
  );
}

export function useSourceDrawer() {
  const ctx = useContext(SourceDrawerContext);
  if (!ctx) throw new Error("useSourceDrawer must be used within SourceDrawerProvider");
  return ctx;
}
