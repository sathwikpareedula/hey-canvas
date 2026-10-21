import type { Course } from "@/lib/domain/types";
import { coursePrimaryTitle } from "@/lib/courses/display";

const STOP_WORDS = new Set([
  "a",
  "an",
  "the",
  "my",
  "me",
  "for",
  "to",
  "in",
  "on",
  "of",
  "and",
  "or",
  "next",
  "this",
  "that",
  "make",
  "help",
  "prepared",
  "prepare",
  "exam",
  "test",
  "quiz",
  "assignment",
  "due",
  "what",
  "whats",
  "have",
  "i",
  "am",
  "is",
  "are",
  "course",
  "class",
]);

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length >= 3 && !STOP_WORDS.has(t));
}

function editDistanceAtMost(a: string, b: string, max: number): boolean {
  if (a === b) return true;
  if (Math.abs(a.length - b.length) > max) return false;
  const rows = a.length + 1;
  const cols = b.length + 1;
  let prev = new Array<number>(cols);
  let curr = new Array<number>(cols);
  for (let j = 0; j < cols; j += 1) prev[j] = j;
  for (let i = 1; i < rows; i += 1) {
    curr[0] = i;
    let rowMin = curr[0];
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
      rowMin = Math.min(rowMin, curr[j]);
    }
    if (rowMin > max) return false;
    [prev, curr] = [curr, prev];
  }
  return prev[b.length]! <= max;
}

function hayWords(hay: string): string[] {
  return hay.split(/\s+/).filter((w) => w.length >= 3);
}

function tokenMatchesHay(token: string, hay: string): boolean {
  if (hay.includes(token)) return true;
  if (token.endsWith("ics") && token.length > 5) {
    const stem = token.slice(0, -3);
    if (hay.includes(stem)) return true;
  }
  if (token.endsWith("s") && token.length > 4 && hay.includes(token.slice(0, -1))) return true;
  if (token.length >= 5) {
    for (const word of hayWords(hay)) {
      if (word.length >= 5 && editDistanceAtMost(token, word, 2)) return true;
    }
  }
  return false;
}

function courseSearchHaystack(course: Course): string {
  const primary = coursePrimaryTitle(course).toLowerCase();
  const name = (course.name ?? "").toLowerCase();
  const code = (course.code ?? "").toLowerCase();
  return `${primary} ${name} ${code}`;
}

export interface CourseTextMatchResult {
  outcome: "resolved" | "ambiguous" | "unresolved";
  courseId: string | null;
  candidates: Course[];
}

/** Match synced courses from free text — never silently pick when multiple plausible. */
export function matchCoursesFromUserText(
  text: string,
  catalog: Course[],
): CourseTextMatchResult {
  const trimmed = text.trim();
  if (!trimmed || catalog.length === 0) {
    return { outcome: "unresolved", courseId: null, candidates: [] };
  }

  const tokens = tokenize(trimmed);
  if (tokens.length === 0) {
    return { outcome: "unresolved", courseId: null, candidates: [] };
  }

  const scored = catalog
    .map((course) => {
      const hay = courseSearchHaystack(course);
      let score = 0;
      for (const token of tokens) {
        if (tokenMatchesHay(token, hay)) score += 1;
      }
      const compactHay = hay.replace(/\s+/g, "");
      const compactQuery = trimmed.toLowerCase().replace(/\s+/g, "");
      if (compactHay.includes(compactQuery) && compactQuery.length >= 5) score += 3;
      return { course, score };
    })
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score);

  if (scored.length === 0) {
    return { outcome: "unresolved", courseId: null, candidates: [] };
  }

  const top = scored[0]!;
  const tied = scored.filter((s) => s.score === top.score).map((s) => s.course);
  if (tied.length === 1) {
    return { outcome: "resolved", courseId: top.course.id, candidates: [top.course] };
  }
  return { outcome: "ambiguous", courseId: null, candidates: tied.slice(0, 6) };
}
