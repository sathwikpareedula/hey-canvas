const OBJECT_TAG = /\[object Object\]/gi;

/** Safe user-visible string; never returns undefined, NaN, or [object Object]. */
export function displayText(value: unknown, fallback = ""): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return fallback;
    return String(value);
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed || trimmed === "undefined" || trimmed === "NaN") return fallback;
    return trimmed.replace(OBJECT_TAG, fallback).trim() || fallback;
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return fallback;
}

export function displayOptionalText(value: unknown): string | undefined {
  const text = displayText(value, "");
  return text ? text : undefined;
}
