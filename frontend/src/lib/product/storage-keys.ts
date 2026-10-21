/** Approved localStorage keys for product preferences (no academic document bodies). */

export const PRODUCT_STORAGE_KEYS = {
  onboarding: "hey-canvas-onboarding-v1",
  focusCourses: "hey-canvas-focus-courses-v1",
  aiPreferences: "hey-canvas-ai-preferences-v1",
  courseAiPolicies: "hey-canvas-course-ai-policies-v1",
} as const;

export type ProductStorageKey = (typeof PRODUCT_STORAGE_KEYS)[keyof typeof PRODUCT_STORAGE_KEYS];
