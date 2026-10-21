/** Strict loopback checks shared by the Next.js request boundary. */

const LOOPBACK_NAMES = new Set(["localhost", "127.0.0.1", "::1"]);
const HOST_PATTERN =
  /^(\[[0-9a-fA-F:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)(?::([0-9]{1,5}))?$/;

/** Accept only a present, well-formed Host header naming this computer. */
export function isLoopbackHostHeader(raw: string | null | undefined): boolean {
  if (!raw) {
    return false;
  }
  const match = HOST_PATTERN.exec(raw.trim());
  if (!match) {
    return false;
  }
  if (match[2] !== undefined && Number(match[2]) > 65535) {
    return false;
  }
  const host = match[1].toLowerCase().replace(/^\[|\]$/g, "");
  return LOOPBACK_NAMES.has(host);
}

/** Accept only a bare http(s) origin (no userinfo, path, query or fragment) on loopback. */
export function isLoopbackOrigin(raw: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(raw.trim());
  } catch {
    return false;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return false;
  }
  if (parsed.username || parsed.password) {
    return false;
  }
  if (parsed.pathname !== "/" || parsed.search || parsed.hash) {
    return false;
  }
  return LOOPBACK_NAMES.has(parsed.hostname.toLowerCase().replace(/^\[|\]$/g, ""));
}
