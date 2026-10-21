/** Backend origin for server-side proxying (build-time env, same default as next.config rewrites). */
export function resolveBackendOrigin(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}
