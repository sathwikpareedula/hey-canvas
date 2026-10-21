import type { AcademicApi } from "@/lib/api/academic-api";
import { getApiMode } from "@/lib/api/app-mode";
import { HttpAcademicApi } from "@/lib/api/http-academic-api";
import { MockAcademicApi } from "@/lib/api/mock-academic-api";

export type { ApiMode } from "@/lib/api/app-mode";
export { getApiMode, isExplicitDemoMode } from "@/lib/api/app-mode";

let singleton: AcademicApi | null = null;

/** Server and client safe — HTTP/personal by default; mock only when explicitly configured. */
export function getAcademicApi(): AcademicApi {
  if (singleton) return singleton;
  const mode = getApiMode();
  singleton = mode === "http" ? new HttpAcademicApi() : new MockAcademicApi();
  return singleton;
}

export { type AcademicApi } from "@/lib/api/academic-api";
