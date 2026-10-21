import { getApiMode } from "@/lib/api/app-mode";
import { fetchHealth } from "@/lib/api/http/fetch-json";
import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";

export type BackendConnectionState = "mock" | "connected" | "unavailable";

export async function probeBackendConnection(): Promise<BackendConnectionState> {
  if (getApiMode() === "mock") return "mock";
  const ok = await fetchHealth(resolveApiBaseUrl());
  return ok ? "connected" : "unavailable";
}
