import { isExplicitDemoMode } from "@/lib/api/app-mode";
import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";

export interface AssistantRuntimeStatus {
  configured: boolean;
  provider: string;
  available: boolean | null;
}

export async function fetchAssistantRuntimeStatus(): Promise<AssistantRuntimeStatus | null> {
  const base = resolveApiBaseUrl();
  try {
    const res = await fetch(`${base}/api/assistant/status`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as AssistantRuntimeStatus;
  } catch {
    return null;
  }
}

export function describeAssistantRuntimeStatus(status: AssistantRuntimeStatus | null): string {
  if (!status) return "Local AI status unavailable";
  if (!status.configured) return "Local AI is not set up on this computer yet";
  if (status.provider === "synthetic" && isExplicitDemoMode()) {
    return "Demo assistant ready (synthetic data)";
  }
  if (status.provider === "synthetic") {
    return "Local AI is not configured — open Settings to choose a model";
  }
  if (status.available === false) return "Local AI runtime is not reachable";
  if (status.available === null) return "Local AI configured";
  return status.available ? "Local AI ready" : "Local AI unavailable";
}
