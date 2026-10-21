import { PRODUCT_STORAGE_KEYS } from "@/lib/product/storage-keys";

export type InstructorAiPolicy = "unknown" | "allowed" | "restricted" | "disabled";

export type CourseCloudPolicy = "allowed" | "local_only";

export interface CourseAiPolicyRecord {
  instructorPolicy: InstructorAiPolicy;
  cloudProcessing: CourseCloudPolicy;
  notes: string;
}

export type CourseAiPolicyMap = Record<string, CourseAiPolicyRecord>;

const DEFAULT_RECORD: CourseAiPolicyRecord = {
  instructorPolicy: "unknown",
  cloudProcessing: "local_only",
  notes: "",
};

export function readCourseAiPolicies(): CourseAiPolicyMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(PRODUCT_STORAGE_KEYS.courseAiPolicies);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as CourseAiPolicyMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writeCourseAiPolicies(map: CourseAiPolicyMap): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRODUCT_STORAGE_KEYS.courseAiPolicies, JSON.stringify(map));
}

export function getCourseAiPolicy(courseId: string): CourseAiPolicyRecord {
  const map = readCourseAiPolicies();
  return map[courseId] ?? { ...DEFAULT_RECORD };
}

export function saveCourseAiPolicy(courseId: string, patch: Partial<CourseAiPolicyRecord>): CourseAiPolicyRecord {
  const map = readCourseAiPolicies();
  const current = map[courseId] ?? { ...DEFAULT_RECORD };
  const next: CourseAiPolicyRecord = {
    instructorPolicy: patch.instructorPolicy ?? current.instructorPolicy,
    cloudProcessing: patch.cloudProcessing ?? current.cloudProcessing,
    notes: patch.notes ?? current.notes,
  };
  map[courseId] = next;
  writeCourseAiPolicies(map);
  return next;
}

export function instructorAiPolicyLabel(policy: InstructorAiPolicy): string {
  switch (policy) {
    case "allowed":
      return "Allowed (per your notes)";
    case "restricted":
      return "Restricted";
    case "disabled":
      return "Disabled";
    default:
      return "Unknown";
  }
}

export function policyBlocksCloudUse(record: CourseAiPolicyRecord): boolean {
  return record.cloudProcessing === "local_only" || record.instructorPolicy === "disabled";
}

export const AI_POLICY_DISCLAIMER =
  "Hey Canvas does not decide whether your instructor allows AI. Follow your course, department, and institution rules.";
