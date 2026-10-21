/** Safe user-facing message from FastAPI-style error bodies. */

const INTERNAL_PATTERNS = [
  /traceback/i,
  /sqlalchemy/i,
  /exception at/i,
  /file ".*\.py"/i,
];

export function messageFromHttpErrorBody(
  status: number,
  bodyText: string,
): string {
  const trimmed = bodyText.trim();
  if (!trimmed) return `Request failed (${status})`;

  try {
    const json = JSON.parse(trimmed) as { detail?: unknown };
    const detail = json.detail;
    if (typeof detail === "string" && detail.trim()) {
      return sanitizeUserFacingDetail(detail.trim());
    }
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return null;
        })
        .filter((s): s is string => Boolean(s));
      if (parts.length) return sanitizeUserFacingDetail(parts.join(" "));
    }
  } catch {
    // not JSON
  }

  if (trimmed.length <= 280 && !looksInternal(trimmed)) {
    return sanitizeUserFacingDetail(trimmed);
  }

  return `Request failed (${status})`;
}

function looksInternal(text: string): boolean {
  return INTERNAL_PATTERNS.some((re) => re.test(text));
}

function sanitizeUserFacingDetail(text: string): string {
  if (looksInternal(text)) return "Something went wrong. Try again.";
  return text;
}
