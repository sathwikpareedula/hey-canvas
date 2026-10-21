/** Parse a finite number or return fallback (never NaN). */
export function finiteNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

export function finitePercent(value: unknown, fallback = 0): number {
  const n = finiteNumber(value, fallback);
  return Math.min(100, Math.max(0, Math.round(n)));
}
