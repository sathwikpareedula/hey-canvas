import type { Assignment } from "@/lib/domain/types";
import { parseChicagoDate } from "@/lib/utils/chicago-date";

const CHICAGO = "America/Chicago";

function chicagoParts(date: Date): { y: number; m: number; d: number } {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: CHICAGO,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = fmt.formatToParts(date);
  const y = Number(parts.find((p) => p.type === "year")?.value);
  const m = Number(parts.find((p) => p.type === "month")?.value);
  const d = Number(parts.find((p) => p.type === "day")?.value);
  return { y, m, d };
}

/** Sunday-start calendar week in America/Chicago. */
export function startOfChicagoWeek(date: Date): Date {
  const { y, m, d } = chicagoParts(date);
  const utcMid = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
  const weekday = new Intl.DateTimeFormat("en-US", {
    timeZone: CHICAGO,
    weekday: "short",
  }).format(utcMid);
  const map: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  const dow = map[weekday.slice(0, 3)] ?? 0;
  const start = new Date(utcMid);
  start.setUTCDate(start.getUTCDate() - dow);
  return start;
}

export function isDueInFuture(iso: string | null | undefined, now = new Date()): boolean {
  const due = parseChicagoDate(iso);
  if (!due) return false;
  return due.getTime() > now.getTime();
}

export function isNextChicagoCalendarWeek(
  iso: string | null | undefined,
  now = new Date(),
): boolean {
  const due = parseChicagoDate(iso);
  if (!due) return false;
  const thisWeekStart = startOfChicagoWeek(now);
  const nextWeekStart = new Date(thisWeekStart);
  nextWeekStart.setUTCDate(nextWeekStart.getUTCDate() + 7);
  const nextWeekEnd = new Date(nextWeekStart);
  nextWeekEnd.setUTCDate(nextWeekEnd.getUTCDate() + 7);
  const t = due.getTime();
  return t >= nextWeekStart.getTime() && t < nextWeekEnd.getTime();
}

export function compareDueAscending(a: Assignment, b: Assignment): number {
  const ad = a.dueAt ?? "";
  const bd = b.dueAt ?? "";
  if (!ad && !bd) return a.title.localeCompare(b.title);
  if (!ad) return 1;
  if (!bd) return -1;
  return ad.localeCompare(bd);
}

export function pickNextDeadline(
  assignments: Assignment[],
  now = new Date(),
): Assignment | null {
  const future = assignments
    .filter((a) => isDueInFuture(a.dueAt, now))
    .sort(compareDueAscending);
  return future[0] ?? null;
}

export function filterUpcomingAssignments(
  assignments: Assignment[],
  now = new Date(),
  limit = 5,
): Assignment[] {
  return assignments
    .filter(
      (a) =>
        isDueInFuture(a.dueAt, now) &&
        a.deadlineWindow !== "past_due_time",
    )
    .sort(compareDueAscending)
    .slice(0, limit);
}

export function filterAssignmentsForNextWeek(
  assignments: Assignment[],
  now = new Date(),
): Assignment[] {
  return assignments
    .filter((a) => isNextChicagoCalendarWeek(a.dueAt, now))
    .sort(compareDueAscending);
}
