"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import { useProductSetup } from "@/contexts/ProductSetupContext";

const ALLOWED_WITHOUT_SETUP = ["/onboarding", "/settings", "/startup"];

export function OnboardingGate({ children }: { children: React.ReactNode }) {
  const { onboarding, completeSetup, isHydrated } = useProductSetup();
  const { settings, loading: settingsLoading } = useProductSettings();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!isHydrated || settingsLoading) return;
    if (!onboarding.completed && (settings?.focusCourseIds?.length ?? 0) > 0) {
      completeSetup();
    }
  }, [isHydrated, settingsLoading, onboarding.completed, settings?.focusCourseIds, completeSetup]);

  useEffect(() => {
    if (!isHydrated || settingsLoading) return;
    if (onboarding.completed) return;
    if ((settings?.focusCourseIds?.length ?? 0) > 0) return;
    if (ALLOWED_WITHOUT_SETUP.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
      return;
    }
    router.replace("/onboarding");
  }, [isHydrated, settingsLoading, onboarding.completed, settings?.focusCourseIds, pathname, router]);

  return children;
}
