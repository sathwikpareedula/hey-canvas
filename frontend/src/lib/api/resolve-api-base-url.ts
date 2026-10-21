/** Browser HTTP mode uses same-origin proxy; server/tests use explicit base URL. */
export function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_ACADEMIC_API_MODE !== "mock") {
    return "";
  }
  return configured.replace(/\/$/, "");
}
