"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  advanceOnboarding,
  completeOnboarding,
  readOnboardingState,
  retreatOnboarding,
  resumeOnboardingAt,
  type OnboardingState,
  type OnboardingStepId,
} from "@/lib/product/onboarding";
import {
  readAiPreferences,
  saveAiPreferences,
  type AiPreferences,
} from "@/lib/product/ai-preferences";

interface ProductSetupContextValue {
  onboarding: OnboardingState;
  aiPreferences: AiPreferences;
  isHydrated: boolean;
  completeSetup: () => void;
  goToStep: (step: OnboardingStepId) => void;
  nextStep: () => void;
  prevStep: () => void;
  updateAiPreferences: (patch: Partial<Omit<AiPreferences, "version" | "updatedAt">>) => void;
  reload: () => void;
}

const ProductSetupContext = createContext<ProductSetupContextValue | null>(null);

const DEFAULT_ONBOARDING: OnboardingState = {
  version: 1,
  completed: false,
  currentStep: "welcome",
  updatedAt: new Date(0).toISOString(),
};

const DEFAULT_AI: AiPreferences = {
  version: 1,
  processingMode: "local",
  localModelTier: "recommended",
  updatedAt: new Date(0).toISOString(),
};

export function ProductSetupProvider({ children }: { children: React.ReactNode }) {
  const [onboarding, setOnboarding] = useState<OnboardingState>(DEFAULT_ONBOARDING);
  const [aiPreferences, setAiPreferences] = useState<AiPreferences>(DEFAULT_AI);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Synchronous hydration of local-storage state on mount
    setOnboarding(readOnboardingState());
    setAiPreferences(readAiPreferences());
    setIsHydrated(true);
  }, []);


  const reload = useCallback(() => {
    setOnboarding(readOnboardingState());
    setAiPreferences(readAiPreferences());
  }, []);

  const completeSetup = useCallback(() => {
    setOnboarding(completeOnboarding());
  }, []);

  const goToStep = useCallback((step: OnboardingStepId) => {
    setOnboarding(resumeOnboardingAt(step));
  }, []);

  const nextStep = useCallback(() => {
    setOnboarding((prev) => advanceOnboarding(prev.currentStep));
  }, []);

  const prevStep = useCallback(() => {
    setOnboarding((prev) => retreatOnboarding(prev.currentStep));
  }, []);

  const updateAiPreferences = useCallback(
    (patch: Partial<Omit<AiPreferences, "version" | "updatedAt">>) => {
      setAiPreferences(saveAiPreferences(patch));
    },
    [],
  );

  const value = useMemo(
    () => ({
      onboarding,
      aiPreferences,
      isHydrated,
      completeSetup,
      goToStep,
      nextStep,
      prevStep,
      updateAiPreferences,
      reload,
    }),
    [
      onboarding,
      aiPreferences,
      isHydrated,
      completeSetup,
      goToStep,
      nextStep,
      prevStep,
      updateAiPreferences,
      reload,
    ],
  );

  return (
    <ProductSetupContext.Provider value={value}>{children}</ProductSetupContext.Provider>
  );
}

export function useProductSetup(): ProductSetupContextValue {
  const ctx = useContext(ProductSetupContext);
  if (!ctx) throw new Error("useProductSetup requires ProductSetupProvider");
  return ctx;
}
