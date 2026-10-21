/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  canSkipFocusCourseStep,
  nextOnboardingStep,
  ONBOARDING_STEP_ORDER,
  onboardingResumeTarget,
  previousOnboardingStep,
  normalizeOnboardingStep,
  type OnboardingState,
} from "@/lib/product/onboarding";

describe("onboarding", () => {
  it("walks steps forward and back", () => {
    expect(nextOnboardingStep("welcome")).toBe("sync");
    expect(previousOnboardingStep("focus")).toBe("sync");
    expect(ONBOARDING_STEP_ORDER.at(-1)).toBe("ready");
  });

  it("resumes at saved step instead of skipping to ready", () => {
    const mid: OnboardingState = {
      version: 1,
      completed: false,
      currentStep: "focus",
      updatedAt: new Date().toISOString(),
    };
    expect(onboardingResumeTarget(mid)).toBe("focus");
    expect(onboardingResumeTarget({ ...mid, completed: true })).toBe("ready");
  });

  it("allows skipping focus when catalog is empty", () => {
    expect(canSkipFocusCourseStep(0)).toBe(true);
    expect(canSkipFocusCourseStep(3)).toBe(false);
  });

  it("normalizes legacy canvas and privacy steps", () => {
    expect(normalizeOnboardingStep("canvas")).toBe("sync");
    expect(normalizeOnboardingStep("privacy")).toBe("sync");
  });
});
