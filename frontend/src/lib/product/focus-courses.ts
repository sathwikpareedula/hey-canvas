import type { Course } from "@/lib/domain/types";
import { PRODUCT_STORAGE_KEYS } from "@/lib/product/storage-keys";

export interface FocusCoursesSnapshot {
  version: 1;
  focusCourseIds: string[];
  /** Term label when focus was last saved — used for rollover hints. */
  termHint: string | null;
  updatedAt: string;
}

const EMPTY: FocusCoursesSnapshot = {
  version: 1,
  focusCourseIds: [],
  termHint: null,
  updatedAt: new Date(0).toISOString(),
};

export function readFocusCoursesSnapshot(): FocusCoursesSnapshot {
  if (typeof window === "undefined") return EMPTY;
  try {
    const raw = window.localStorage.getItem(PRODUCT_STORAGE_KEYS.focusCourses);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as FocusCoursesSnapshot;
    if (parsed?.version !== 1 || !Array.isArray(parsed.focusCourseIds)) return EMPTY;
    return {
      version: 1,
      focusCourseIds: parsed.focusCourseIds.filter((id) => typeof id === "string"),
      termHint: typeof parsed.termHint === "string" ? parsed.termHint : null,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : EMPTY.updatedAt,
    };
  } catch {
    return EMPTY;
  }
}

export function writeFocusCoursesSnapshot(snapshot: FocusCoursesSnapshot): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRODUCT_STORAGE_KEYS.focusCourses, JSON.stringify(snapshot));
}

export function saveFocusCourseIds(
  focusCourseIds: string[],
  termHint: string | null,
): FocusCoursesSnapshot {
  const next: FocusCoursesSnapshot = {
    version: 1,
    focusCourseIds: [...new Set(focusCourseIds.filter(Boolean))],
    termHint,
    updatedAt: new Date().toISOString(),
  };
  writeFocusCoursesSnapshot(next);
  return next;
}

export function toggleFocusCourseId(courseId: string, focusIds: string[]): string[] {
  const set = new Set(focusIds);
  if (set.has(courseId)) set.delete(courseId);
  else set.add(courseId);
  return [...set];
}

/** Focus courses that still exist in the catalog, preserving order. */
export function resolveFocusCourses(
  focusIds: string[],
  catalog: Course[],
): Course[] {
  const byId = new Map(catalog.map((c) => [c.id, c]));
  return focusIds.map((id) => byId.get(id)).filter((c): c is Course => Boolean(c));
}

export function suggestInitialFocusCourseIds(
  catalog: Course[],
  max = 6,
): string[] {
  const buckets = bucketCoursesForFocus(catalog);
  const picked: string[] = [];
  for (const course of buckets.likelyCurrent) {
    if (picked.length >= max) break;
    picked.push(course.id);
  }
  for (const course of buckets.otherCurrent) {
    if (picked.length >= max) break;
    if (!picked.includes(course.id)) picked.push(course.id);
  }
  return picked;
}

export interface CourseFocusBuckets {
  likelyCurrent: Course[];
  otherCurrent: Course[];
  past: Course[];
  trainingOrResources: Course[];
}

const TRAINING_PATTERN =
  /\b(training|orientation|sandbox|demo|practice course|resources only|non-?credit|concur|benchmark|skills?\s*assessment|advising|advisor|lab\s*safety|mav\s*swap|math\s*placement|work\s*study|placement\s*exam|evergreen)\b/i;

export function inferDominantTerm(courses: Course[]): string | null {
  const counts = new Map<string, number>();
  for (const c of courses) {
    const term = c.term?.trim();
    if (!term) continue;
    counts.set(term, (counts.get(term) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [term, count] of counts) {
    if (count > bestCount) {
      best = term;
      bestCount = count;
    }
  }
  return best;
}

function parseTermYear(term: string): number | null {
  const match = term.match(/\b(20\d{2})\b/);
  return match ? Number(match[1]) : null;
}

export function bucketCoursesForFocus(catalog: Course[]): CourseFocusBuckets {
  const dominant = inferDominantTerm(catalog);
  const dominantYear = dominant ? parseTermYear(dominant) : null;
  const currentYear = new Date().getFullYear();

  const likelyCurrent: Course[] = [];
  const otherCurrent: Course[] = [];
  const past: Course[] = [];
  const trainingOrResources: Course[] = [];

  for (const course of catalog) {
    if (TRAINING_PATTERN.test(course.name) || TRAINING_PATTERN.test(course.code ?? "")) {
      trainingOrResources.push(course);
      continue;
    }
    const term = course.term?.trim() ?? "";
    const year = term ? parseTermYear(term) : null;
    if (dominant && term === dominant) {
      likelyCurrent.push(course);
      continue;
    }
    if (year != null && dominantYear != null && year < dominantYear) {
      past.push(course);
      continue;
    }
    if (year != null && year < currentYear - 1) {
      past.push(course);
      continue;
    }
    if (term) otherCurrent.push(course);
    else otherCurrent.push(course);
  }

  const byName = (a: Course, b: Course) => a.name.localeCompare(b.name);
  likelyCurrent.sort(byName);
  otherCurrent.sort(byName);
  past.sort(byName);
  trainingOrResources.sort(byName);

  return { likelyCurrent, otherCurrent, past, trainingOrResources };
}

export function focusRolloverHint(
  snapshot: FocusCoursesSnapshot,
  catalog: Course[],
): string | null {
  const dominant = inferDominantTerm(catalog);
  if (dominant && snapshot.termHint && snapshot.termHint !== dominant) {
    return `Your saved focus courses are from ${snapshot.termHint}. ${dominant} courses are available — review Focus Courses in Settings.`;
  }
  const resolved = resolveFocusCourses(snapshot.focusCourseIds, catalog);
  if (snapshot.focusCourseIds.length > 0 && resolved.length === 0) {
    return "None of your saved focus courses are in the current catalog. Choose focus courses for this term.";
  }
  return null;
}
