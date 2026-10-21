/**
 * Deterministic synthetic student catalogs for generic product simulation.
 * No institution-specific Canvas IDs — ids are generated from archetype + variant seeds.
 */
import type { Assignment, Course, DeadlinesGrouped } from "@/lib/domain/types";
import { inferDominantTerm } from "@/lib/product/focus-courses";

export const STUDENT_ARCHETYPE_IDS = [
  "one_active_course",
  "three_active_courses",
  "five_active_courses",
  "eight_active_courses",
  "twenty_mixed_catalog",
  "no_historical_courses",
  "many_historical_courses",
  "advising_training_shells",
  "duplicate_course_names",
  "long_course_names",
  "punctuation_course_names",
  "course_codes_only",
  "no_assignments",
  "hundreds_of_assignments",
  "no_materials",
  "many_materials",
  "duplicate_assignment_names",
  "duplicate_lecture_names",
  "canvas_course_disappeared",
  "term_changes",
  "no_focus_courses",
  "all_courses_focus",
  "one_focus_course",
  "local_ai_unavailable",
  "no_model_selected",
  "cached_offline",
  "no_canvas_sync_yet",
  "stale_canvas_sync",
  "malicious_professor_material",
  "unsupported_material_type",
] as const;

export type StudentArchetypeId = (typeof STUDENT_ARCHETYPE_IDS)[number];

export type SyncState = "never" | "fresh" | "stale";
export type LocalAiState = "ready" | "unavailable" | "needs_model" | "selected_missing";

export interface SyntheticStudentProfile {
  id: string;
  archetype: StudentArchetypeId;
  variant: number;
  catalog: Course[];
  /** Saved focus ids (may include stale ids for rollover/disappear archetypes). */
  focusCourseIds: string[];
  termHint: string | null;
  assignments: Assignment[];
  deadlines: DeadlinesGrouped;
  overdue: Assignment[];
  sync: SyncState;
  localAi: {
    state: LocalAiState;
    selectedModel: string | null;
    installed: string[];
  };
  /** Opaque tags for matrix expectations. */
  flags: {
    expectsOnboarding: boolean;
    expectsRolloverHint: boolean;
    hasDuplicateCourseNames: boolean;
    hasTrainingShells: boolean;
  };
}

function mulberry32(seed: number): () => number {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function courseId(archetype: StudentArchetypeId, variant: number, index: number): string {
  const h = `${archetype}:${variant}:${index}`;
  let hash = 0;
  for (let i = 0; i < h.length; i += 1) hash = (hash * 31 + h.charCodeAt(i)) | 0;
  return `course-${(hash >>> 0).toString(36)}`;
}

function baseTerm(archetype: StudentArchetypeId): string {
  if (archetype === "term_changes") return "Spring 2026";
  if (archetype === "many_historical_courses") return "Spring 2026";
  return "Fall 2026";
}

function pastTerm(current: string): string {
  if (current.includes("2026")) return "Fall 2025";
  return "Fall 2024";
}

function buildCourses(archetype: StudentArchetypeId, variant: number): Course[] {
  const rng = mulberry32(variant * 9973 + archetype.length * 131);
  const term = baseTerm(archetype);
  const past = pastTerm(term);
  const courses: Course[] = [];

  const activeTarget = (() => {
    switch (archetype) {
      case "one_active_course":
      case "one_focus_course":
      case "no_assignments":
      case "no_materials":
        return 1;
      case "three_active_courses":
        return 3;
      case "five_active_courses":
        return 5;
      case "eight_active_courses":
        return 8;
      case "twenty_mixed_catalog":
        return 12;
      case "hundreds_of_assignments":
        return 3;
      case "many_materials":
        return 4;
      default:
        return 4 + (variant % 3);
    }
  })();

  const pastTarget =
    archetype === "no_historical_courses"
      ? 0
      : archetype === "many_historical_courses"
        ? 14
        : archetype === "twenty_mixed_catalog"
          ? 8
          : archetype === "canvas_course_disappeared"
            ? 0
            : Math.min(6, Math.floor(rng() * 4));

  const trainingTarget =
    archetype === "advising_training_shells" || archetype === "twenty_mixed_catalog" ? 3 : 0;

  const nameFor = (kind: "active" | "past" | "training", index: number): { name: string; code: string } => {
    if (archetype === "duplicate_course_names") {
      return { name: "Introduction to Computing", code: `CMP ${1000 + index}` };
    }
    if (archetype === "long_course_names") {
      return {
        name: `Advanced Topics in ${"Interdisciplinary ".repeat(6)}Studies ${index}`,
        code: `GEN ${2000 + index}`,
      };
    }
    if (archetype === "punctuation_course_names") {
      return { name: `Data & Ethics (Honors) — Section ${index + 1}`, code: `HON-${index}` };
    }
    if (archetype === "course_codes_only") {
      return { name: `BIO ${1100 + index}`, code: `BIO ${1100 + index}` };
    }
    if (kind === "training") {
      const labels = ["Faculty Training Sandbox", "Undergraduate Advising", "Lab Safety Orientation"];
      return { name: labels[index % labels.length]!, code: `TRN-${index}` };
    }
    return {
      name: `${kind === "past" ? "Archived" : "Active"} Course ${index + 1}`,
      code: `SUBJ ${3000 + index}`,
    };
  };

  let idx = 0;
  for (let i = 0; i < activeTarget; i += 1, idx += 1) {
    const { name, code } = nameFor("active", i);
    courses.push({ id: courseId(archetype, variant, idx), name, code, term });
  }
  for (let i = 0; i < pastTarget; i += 1, idx += 1) {
    const { name, code } = nameFor("past", i);
    courses.push({ id: courseId(archetype, variant, idx), name, code, term: past });
  }
  for (let i = 0; i < trainingTarget; i += 1, idx += 1) {
    const { name, code } = nameFor("training", i);
    courses.push({ id: courseId(archetype, variant, idx), name, code, term });
  }

  return courses;
}

function buildAssignments(
  archetype: StudentArchetypeId,
  variant: number,
  catalog: Course[],
): { assignments: Assignment[]; deadlines: DeadlinesGrouped; overdue: Assignment[] } {
  const empty: DeadlinesGrouped = { today: [], tomorrow: [], thisWeek: [] };
  if (archetype === "no_assignments" || catalog.length === 0) {
    return { assignments: [], deadlines: empty, overdue: [] };
  }

  const now = new Date("2026-10-04T12:00:00Z");
  const iso = (offsetDays: number, hour = 23) =>
    new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + offsetDays, hour, 0)).toISOString();

  const assignments: Assignment[] = [];
  const perCourse =
    archetype === "hundreds_of_assignments"
      ? 120
      : archetype === "duplicate_assignment_names"
        ? 4
        : 2 + (variant % 3);

  catalog.slice(0, archetype === "hundreds_of_assignments" ? 3 : catalog.length).forEach((course, cIdx) => {
    for (let i = 0; i < perCourse; i += 1) {
      const title =
        archetype === "duplicate_assignment_names"
          ? "Weekly Reflection"
          : `Assignment ${cIdx + 1}.${i + 1}`;
      const dueAt = iso((i % 7) - 2, 23);
      assignments.push({
        id: `asg-${course.id}-${i}`,
        courseId: course.id,
        title,
        dueAt,
      });
    }
  });

  const today = assignments.filter((a) => a.dueAt?.startsWith(iso(0).slice(0, 10)));
  const tomorrow = assignments.filter((a) => a.dueAt?.startsWith(iso(1).slice(0, 10)));
  const thisWeek = assignments.filter((a) => {
    if (!a.dueAt) return false;
    const d = Date.parse(a.dueAt);
    const start = Date.parse(iso(0));
    const end = Date.parse(iso(7));
    return d >= start && d <= end;
  });
  const overdue = assignments.filter((a) => a.dueAt && Date.parse(a.dueAt) < Date.parse(iso(0)));

  return {
    assignments,
    deadlines: {
      today: today.length ? today : assignments.slice(0, 1),
      tomorrow: tomorrow.length ? tomorrow : assignments.slice(1, 2),
      thisWeek: thisWeek.length ? thisWeek : assignments.slice(0, 3),
    },
    overdue,
  };
}

function buildFocusIds(
  archetype: StudentArchetypeId,
  variant: number,
  catalog: Course[],
): { focusCourseIds: string[]; termHint: string | null; staleIds: string[] } {
  const active = catalog.filter((c) => !c.term?.includes("2024") && !c.term?.includes("2025"));
  const ids = active.map((c) => c.id);
  const staleIds: string[] = [];

  switch (archetype) {
    case "no_focus_courses":
      return { focusCourseIds: [], termHint: null, staleIds };
    case "one_focus_course":
      return { focusCourseIds: ids.slice(0, 1), termHint: catalog[0]?.term ?? null, staleIds };
    case "all_courses_focus":
      return { focusCourseIds: ids, termHint: catalog[0]?.term ?? null, staleIds };
    case "canvas_course_disappeared":
      staleIds.push("course-removed-by-canvas");
      return {
        focusCourseIds: [...ids.slice(0, 2), "course-removed-by-canvas"],
        termHint: "Fall 2025",
        staleIds,
      };
    case "term_changes":
      return {
        focusCourseIds: ids.slice(0, Math.min(3, ids.length)),
        termHint: "Fall 2025",
        staleIds,
      };
    default:
      return {
        focusCourseIds: ids.slice(0, Math.min(6, ids.length)),
        termHint: catalog[0]?.term ?? null,
        staleIds,
      };
  }
}

function buildLocalAi(archetype: StudentArchetypeId): SyntheticStudentProfile["localAi"] {
  switch (archetype) {
    case "local_ai_unavailable":
      return { state: "unavailable", selectedModel: "llama3:8b", installed: [] };
    case "no_model_selected":
      return { state: "needs_model", selectedModel: null, installed: ["phi3:mini"] };
    case "cached_offline":
      return { state: "ready", selectedModel: "phi3:mini", installed: ["phi3:mini"] };
    default:
      return { state: "ready", selectedModel: "phi3:mini", installed: ["phi3:mini", "llama3:8b"] };
  }
}

export function buildStudentProfile(archetype: StudentArchetypeId, variant: number): SyntheticStudentProfile {
  const catalog = buildCourses(archetype, variant);
  const { assignments, deadlines, overdue } = buildAssignments(archetype, variant, catalog);
  const { focusCourseIds, termHint, staleIds } = buildFocusIds(archetype, variant, catalog);

  const sync: SyncState =
    archetype === "no_canvas_sync_yet"
      ? "never"
      : archetype === "stale_canvas_sync"
        ? "stale"
        : "fresh";

  const dominant = inferDominantTerm(catalog);
  const rolloverMismatch = Boolean(termHint && dominant && termHint !== dominant);
  return {
    id: `${archetype}-v${variant}`,
    archetype,
    variant,
    catalog,
    focusCourseIds,
    termHint,
    assignments,
    deadlines,
    overdue,
    sync,
    localAi: buildLocalAi(archetype),
    flags: {
      expectsOnboarding: focusCourseIds.length === 0 && catalog.length > 0,
      expectsRolloverHint:
        archetype === "canvas_course_disappeared" || staleIds.length > 0 || rolloverMismatch,
      hasDuplicateCourseNames: archetype === "duplicate_course_names",
      hasTrainingShells: archetype === "advising_training_shells",
    },
  };
}

/** Build exactly `count` deterministic student profiles (default 100). */
export function buildStudentProfiles(count = 100): SyntheticStudentProfile[] {
  const profiles: SyntheticStudentProfile[] = [];
  for (let i = 0; i < count; i += 1) {
    const archetype = STUDENT_ARCHETYPE_IDS[i % STUDENT_ARCHETYPE_IDS.length];
    const variant = Math.floor(i / STUDENT_ARCHETYPE_IDS.length);
    profiles.push(buildStudentProfile(archetype, variant));
  }
  return profiles;
}
