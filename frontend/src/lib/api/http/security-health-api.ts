import { fetchJson, postJson } from "@/lib/api/http/fetch-json";
import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";

export type SecurityCheckStatus = "pass" | "warning" | "fail" | "not_checked";

export interface SecurityCheck {
  id: string;
  title: string;
  status: SecurityCheckStatus;
  summary: string;
  detail?: string | null;
}

export interface SecurityHealthReport {
  generated_at: string;
  checks: SecurityCheck[];
  overall: "pass" | "warning" | "fail" | "not_checked";
}

export interface SecureStoreResult {
  stored: boolean;
  message: string;
}

function base() {
  return resolveApiBaseUrl();
}

export async function fetchSecurityHealthSnapshot(): Promise<SecurityHealthReport> {
  return fetchJson<SecurityHealthReport>(`${base()}/api/security/health`);
}

export async function runSecurityHealthChecks(): Promise<SecurityHealthReport> {
  return postJson<SecurityHealthReport>(`${base()}/api/security/health/run`, {
    probe_canvas: true,
    probe_ollama: true,
  });
}

export async function migrateCanvasTokenToSecureStore(): Promise<SecureStoreResult> {
  return postJson<SecureStoreResult>(`${base()}/api/security/credentials/secure-store`, {});
}
