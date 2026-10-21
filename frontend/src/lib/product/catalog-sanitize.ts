import type { Course } from "@/lib/domain/types";
import type { CourseAiPolicyMap } from "@/lib/product/course-ai-policy";

/** Drop focus ids and per-course AI policy entries that are not in the current catalog. */
export function sanitizeFocusAndPoliciesForCatalog(
  focusCourseIds: string[],
  catalog: Course[],
  policies: CourseAiPolicyMap,
): { focusCourseIds: string[]; policies: CourseAiPolicyMap } {
  const valid = new Set(catalog.map((c) => c.id));
  const nextFocus = focusCourseIds.filter((id) => valid.has(id));
  const nextPolicies: CourseAiPolicyMap = {};
  for (const [courseId, record] of Object.entries(policies)) {
    if (valid.has(courseId)) nextPolicies[courseId] = record;
  }
  return { focusCourseIds: nextFocus, policies: nextPolicies };
}
