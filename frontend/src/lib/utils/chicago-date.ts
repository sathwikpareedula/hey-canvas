const CHICAGO = "America/Chicago";

const ISO_LIKE =
  /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/;

export function parseChicagoDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** User-facing date/time in UTA (America/Chicago) with an explicit zone label (CDT/CST). */
export function formatChicagoDateTime(iso: string | null | undefined): string {
  const d = parseChicagoDate(iso);
  if (!d) return "—";
  return d.toLocaleString("en-US", {
    timeZone: CHICAGO,
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function formatChicagoDateTimeRange(
  from: string | null | undefined,
  to: string | null | undefined,
): string {
  const a = formatChicagoDateTime(from);
  const b = formatChicagoDateTime(to);
  if (a === "—" && b === "—") return "—";
  if (a === "—") return b;
  if (b === "—") return a;
  return `${a} → ${b}`;
}

const FIELD_LABELS: Record<string, string> = {
  due_at: "Due date",
  due_date: "Due date",
  lock_at: "Lock date",
  unlock_at: "Unlock date",
  points_possible: "Points",
  name: "Title",
};

export function humanizeChangeFieldName(field: string | null | undefined): string {
  if (!field) return "Change";
  const key = field.toLowerCase();
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return key.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format stored change values for display (ISO datetimes → Chicago). */
export function formatChangeValue(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  const trimmed = value.trim();
  if (ISO_LIKE.test(trimmed)) {
    const d = parseChicagoDate(trimmed);
    if (d) return formatChicagoDateTime(trimmed);
  }
  return trimmed;
}
