"use client";

import { createContext, useContext, useMemo } from "react";
import type { AcademicApi } from "@/lib/api/academic-api";
import { getAcademicApi } from "@/lib/api";

const AcademicApiContext = createContext<AcademicApi | null>(null);

export function AcademicApiProvider({ children }: { children: React.ReactNode }) {
  const api = useMemo(() => getAcademicApi(), []);
  return (
    <AcademicApiContext.Provider value={api}>{children}</AcademicApiContext.Provider>
  );
}

export function useAcademicApi(): AcademicApi {
  const api = useContext(AcademicApiContext);
  if (!api) throw new Error("useAcademicApi must be used within AcademicApiProvider");
  return api;
}
