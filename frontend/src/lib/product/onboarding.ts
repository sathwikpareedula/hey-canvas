import { PRODUCT_STORAGE_KEYS } from "@/lib/product/storage-keys";

export type OnboardingStepId =
  | "welcome"
  | "canvas"
  | "sync"
  | "focus"
  | "local_ai"
  | "privacy"
  | "ready";

export const ONBOARDING_STEP_ORDER: OnboardingStepId[] = [
  "welcome",
  "sync",
  "focus",
  "local_ai",
  "ready",
];

export function normalizeOnboardingStep(step: OnboardingStepId): OnboardingStepId {
  if (step === "canvas" || step === "privacy") return "sync";
  if (!ONBOARDING_STEP_ORDER.includes(step)) return "welcome";
  return step;
}

export interface OnboardingState {
  version: 1;
  completed: boolean;
  currentStep: OnboardingStepId;
  updatedAt: string;
}

const DEFAULT: OnboardingState = {
  version: 1,
  completed: false,
  currentStep: "welcome",
  updatedAt: new Date(0).toISOString(),
};

export function readOnboardingState(): OnboardingState {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = window.localStorage.getItem(PRODUCT_STORAGE_KEYS.onboarding);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw) as OnboardingState;
    if (parsed?.version !== 1) return DEFAULT;
    const step = normalizeOnboardingStep(parsed.currentStep);
    return {
      version: 1,
      completed: Boolean(parsed.completed),
      currentStep: step,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : DEFAULT.updatedAt,
    };
  } catch {
    return DEFAULT;
  }
}

export function writeOnboardingState(state: OnboardingState): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRODUCT_STORAGE_KEYS.onboarding, JSON.stringify(state));
}

/** Restore completion for an existing configured profile on a fresh browser. */
export function shouldRecognizeReturningUser(
  state: OnboardingState,
  settingsLoaded: boolean,
  settingsSource: string | null,
  focusCourseCount: number,
): boolean {
  if (state.completed) return false;
  return settingsLoaded && settingsSource === "server" && focusCourseCount > 0;
}

export function onboardingStepLabel(step: OnboardingStepId): string {
  switch (step) {
    case "welcome":
      return "Welcome";
    case "canvas":
      return "Canvas";
    case "sync":
      return "Sync";
    case "focus":
      return "Focus courses";
    case "local_ai":
      return "Local AI";
    case "privacy":
      return "Privacy";
    case "ready":
      return "Ready";
    default:
      return "Setup";
  }
}

export function nextOnboardingStep(step: OnboardingStepId): OnboardingStepId | null {
  const idx = ONBOARDING_STEP_ORDER.indexOf(step);
  if (idx < 0 || idx >= ONBOARDING_STEP_ORDER.length - 1) return null;
  return ONBOARDING_STEP_ORDER[idx + 1];
}

export function previousOnboardingStep(step: OnboardingStepId): OnboardingStepId | null {
  const idx = ONBOARDING_STEP_ORDER.indexOf(step);
  if (idx <= 0) return null;
  return ONBOARDING_STEP_ORDER[idx - 1];
}

export function advanceOnboarding(step: OnboardingStepId): OnboardingState {
  const next = nextOnboardingStep(step) ?? step;
  const state: OnboardingState = {
    version: 1,
    completed: false,
    currentStep: next,
    updatedAt: new Date().toISOString(),
  };
  writeOnboardingState(state);
  return state;
}

export function retreatOnboarding(step: OnboardingStepId): OnboardingState {
  const prev = previousOnboardingStep(step) ?? step;
  const state: OnboardingState = {
    version: 1,
    completed: false,
    currentStep: prev,
    updatedAt: new Date().toISOString(),
  };
  writeOnboardingState(state);
  return state;
}

export function completeOnboarding(): OnboardingState {
  const state: OnboardingState = {
    version: 1,
    completed: true,
    currentStep: "ready",
    updatedAt: new Date().toISOString(),
  };
  writeOnboardingState(state);
  return state;
}

export function resumeOnboardingAt(step: OnboardingStepId): OnboardingState {
  const state: OnboardingState = {
    version: 1,
    completed: false,
    currentStep: step,
    updatedAt: new Date().toISOString(),
  };
  writeOnboardingState(state);
  return state;
}

/** Step to open when the student chooses “resume setup” from the welcome screen. */
export function onboardingResumeTarget(state: OnboardingState): OnboardingStepId {
  if (state.completed) return "ready";
  if (state.currentStep !== "welcome") return normalizeOnboardingStep(state.currentStep);
  const progressed = state.updatedAt !== DEFAULT.updatedAt;
  return progressed ? "sync" : "sync";
}

export function canSkipFocusCourseStep(catalogCourseCount: number): boolean {
  return catalogCourseCount === 0;
}
