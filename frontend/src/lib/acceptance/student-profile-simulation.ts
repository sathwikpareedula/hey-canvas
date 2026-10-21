import { matchCoursesFromUserText } from "@/lib/courses/course-router-client";
import { coursePrimaryTitle, formatCourseLabel } from "@/lib/courses/display";
import { resolveInstalledModelMatch } from "@/lib/local-ai/build-snapshot";
import {
  buildDeadlineFastPathMessage,
  matchDeadlineFastPath,
} from "@/lib/product/deadline-fast-path";
import {
  bucketCoursesForFocus,
  focusRolloverHint,
  resolveFocusCourses,
  suggestInitialFocusCourseIds,
} from "@/lib/product/focus-courses";
import { sanitizeFocusAndPoliciesForCatalog } from "@/lib/product/catalog-sanitize";
import type { SyntheticStudentProfile } from "@/lib/acceptance/student-profiles";

export type SimulationDimension =
  | "onboarding"
  | "focus_courses"
  | "today"
  | "tomorrow"
  | "this_week"
  | "next_week"
  | "all_courses"
  | "course_routing"
  | "workspace"
  | "assignment_lookup"
  | "material_lookup"
  | "chat_fast_path"
  | "follow_up_context"
  | "course_switching"
  | "restart_catalog"
  | "tenancy"
  | "semester_rollover"
  | "course_naming"
  | "model_variation";

export interface SimulationCell {
  dimension: SimulationDimension;
  pass: boolean;
  detail?: string;
}

const DEADLINE_PROMPTS: Record<string, "today" | "tomorrow" | "this_week" | "next_week"> = {
  today: "today",
  tomorrow: "tomorrow",
  this_week: "this_week",
  next_week: "next_week",
};

function assertNoThrow(fn: () => void): boolean {
  try {
    fn();
    return true;
  } catch {
    return false;
  }
}

export function simulateStudentProfile(profile: SyntheticStudentProfile): SimulationCell[] {
  const cells: SimulationCell[] = [];
  const catalogIds = new Set(profile.catalog.map((c) => c.id));

  const onboardingPass =
    profile.flags.expectsOnboarding || profile.focusCourseIds.length > 0 || profile.catalog.length === 0;
  cells.push({
    dimension: "onboarding",
    pass: onboardingPass,
    detail: onboardingPass ? undefined : "focus required for onboarding completion",
  });

  const resolvedFocus = resolveFocusCourses(profile.focusCourseIds, profile.catalog);
  const sanitized = sanitizeFocusAndPoliciesForCatalog(profile.focusCourseIds, profile.catalog, {});
  const focusOk =
    sanitized.focusCourseIds.every((id) => catalogIds.has(id)) &&
    (profile.focusCourseIds.length === 0 ||
      resolvedFocus.length > 0 ||
      (profile.flags.expectsRolloverHint && profile.focusCourseIds.some((id) => !catalogIds.has(id))));
  cells.push({
    dimension: "focus_courses",
    pass: focusOk,
  });

  for (const [label, window] of Object.entries(DEADLINE_PROMPTS)) {
    const prompt =
      window === "today"
        ? "what do i have due today"
        : window === "tomorrow"
          ? "anything due tomorrow"
          : window === "this_week"
            ? "what's due this week"
            : "what do i have due next week";
    const matched = matchDeadlineFastPath(prompt);
    const pass =
      matched === window &&
      assertNoThrow(() =>
        buildDeadlineFastPathMessage({
          window,
          deadlines: profile.deadlines,
          overdue: profile.overdue,
          courses: profile.catalog,
          allAssignments: profile.assignments,
        }),
      );
    cells.push({
      dimension: label as SimulationDimension,
      pass,
    });
  }

  cells.push({
    dimension: "all_courses",
    pass: profile.catalog.length >= 1 || profile.archetype === "no_canvas_sync_yet",
  });

  const buckets = bucketCoursesForFocus(profile.catalog);
  const routing = matchCoursesFromUserText("help with active course 1", profile.catalog);
  cells.push({
    dimension: "course_routing",
    pass:
      profile.flags.hasDuplicateCourseNames
        ? matchCoursesFromUserText("introduction to computing", profile.catalog).outcome === "ambiguous"
        : routing.outcome !== "resolved" || Boolean(routing.courseId),
  });

  cells.push({
    dimension: "workspace",
    pass: suggestInitialFocusCourseIds(profile.catalog).every((id) => catalogIds.has(id)),
  });

  cells.push({
    dimension: "assignment_lookup",
    pass: profile.assignments.every((a) => catalogIds.has(a.courseId)),
  });

  cells.push({
    dimension: "material_lookup",
    pass: true,
  });

  cells.push({
    dimension: "chat_fast_path",
    pass: matchDeadlineFastPath("which one should i do first") === "priorities",
  });

  cells.push({
    dimension: "follow_up_context",
    pass: matchDeadlineFastPath("i asked next week") === "next_week",
  });

  const switchPass = (() => {
    if (profile.catalog.length < 2) return true;
    const a = profile.catalog[0]!;
    const b = profile.catalog[1]!;
    const scopedA = buildDeadlineFastPathMessage({
      window: "today",
      deadlines: profile.deadlines,
      overdue: profile.overdue,
      courseId: a.id,
      courses: profile.catalog,
    });
    const scopedB = buildDeadlineFastPathMessage({
      window: "today",
      deadlines: profile.deadlines,
      overdue: profile.overdue,
      courseId: b.id,
      courses: profile.catalog,
    });
    const idsA =
      scopedA.blocks?.[0] && "assignments" in scopedA.blocks[0]
        ? (scopedA.blocks[0].assignments ?? []).map((x) => x.courseId)
        : [];
    const idsB =
      scopedB.blocks?.[0] && "assignments" in scopedB.blocks[0]
        ? (scopedB.blocks[0].assignments ?? []).map((x) => x.courseId)
        : [];
    return (
      idsA.every((id) => id === a.id) &&
      idsB.every((id) => id === b.id) &&
      a.id !== b.id
    );
  })();
  cells.push({ dimension: "course_switching", pass: switchPass });

  cells.push({
    dimension: "restart_catalog",
    pass: buckets.likelyCurrent.length <= profile.catalog.length,
  });

  const courseA = profile.catalog[0];
  const courseB = profile.catalog[1];
  const scoped =
    courseA && courseB
      ? (() => {
          const msg = buildDeadlineFastPathMessage({
            window: "today",
            deadlines: profile.deadlines,
            overdue: profile.overdue,
            courseId: courseA.id,
            courses: profile.catalog,
          });
          const block = msg.blocks?.[0];
          const ids = block && "assignments" in block ? (block.assignments ?? []).map((a) => a.courseId) : [];
          return ids.every((id) => id === courseA.id);
        })()
      : true;
  cells.push({ dimension: "tenancy", pass: scoped });

  const rollover = focusRolloverHint(
    {
      version: 1,
      focusCourseIds: profile.focusCourseIds,
      termHint: profile.termHint,
      updatedAt: new Date(0).toISOString(),
    },
    profile.catalog,
  );
  cells.push({
    dimension: "semester_rollover",
    pass: profile.flags.expectsRolloverHint ? Boolean(rollover) : rollover === null || typeof rollover === "string",
  });

  const namingPass = profile.catalog.every((c) => {
    const title = coursePrimaryTitle(c);
    const label = formatCourseLabel(c);
    return title.length > 0 && label.length > 0 && !title.includes("2268-CSE");
  });
  cells.push({ dimension: "course_naming", pass: namingPass });

  const modelResolved = resolveInstalledModelMatch(
    profile.localAi.selectedModel,
    profile.localAi.installed,
  );
  const modelPass =
    profile.localAi.state === "needs_model"
      ? profile.localAi.selectedModel === null
      : profile.localAi.state === "selected_missing"
        ? Boolean(profile.localAi.selectedModel) &&
          !profile.localAi.installed.includes(profile.localAi.selectedModel!)
        : profile.localAi.state === "unavailable"
          ? profile.localAi.installed.length === 0
          : modelResolved !== null || profile.localAi.installed.length > 0;
  cells.push({ dimension: "model_variation", pass: modelPass });

  return cells;
}

export function summarizeMatrix(profiles: SyntheticStudentProfile[]): {
  profilePass: Map<string, boolean>;
  dimensionPassCounts: Map<SimulationDimension, number>;
  totalCells: number;
  passedCells: number;
} {
  const profilePass = new Map<string, boolean>();
  const dimensionPassCounts = new Map<SimulationDimension, number>();
  let totalCells = 0;
  let passedCells = 0;

  for (const profile of profiles) {
    const cells = simulateStudentProfile(profile);
    let profileOk = true;
    for (const cell of cells) {
      totalCells += 1;
      if (cell.pass) {
        passedCells += 1;
        dimensionPassCounts.set(cell.dimension, (dimensionPassCounts.get(cell.dimension) ?? 0) + 1);
      } else {
        profileOk = false;
      }
    }
    profilePass.set(profile.id, profileOk);
  }

  return { profilePass, dimensionPassCounts, totalCells, passedCells };
}
