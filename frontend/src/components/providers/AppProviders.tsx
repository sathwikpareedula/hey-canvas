"use client";

import { Suspense } from "react";
import { AcademicApiProvider } from "@/contexts/AcademicApiContext";
import { BackendStatusProvider } from "@/contexts/BackendStatusContext";
import { ConversationProvider } from "@/contexts/ConversationContext";
import { CourseContextProvider } from "@/contexts/CourseContext";
import { FocusCoursesProvider } from "@/contexts/FocusCoursesContext";
import { ProductSettingsProvider } from "@/contexts/ProductSettingsContext";
import { ProductSetupProvider } from "@/contexts/ProductSetupContext";
import { NotificationProvider } from "@/contexts/NotificationContext";
import { PreferencesProvider } from "@/contexts/PreferencesContext";
import { SourceDrawerProvider } from "@/contexts/SourceDrawerContext";
import { KeyboardShortcuts } from "@/components/keyboard/KeyboardShortcuts";
import { ServiceWorkerRegister } from "@/components/pwa/ServiceWorkerRegister";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <PreferencesProvider>
      <ProductSetupProvider>
        <AcademicApiProvider>
          <BackendStatusProvider>
            <NotificationProvider>
              <SourceDrawerProvider>
                <ConversationProvider>
                  <Suspense fallback={null}>
                    <ProductSettingsProvider>
                      <FocusCoursesProvider>
                        <CourseContextProvider>{children}</CourseContextProvider>
                      </FocusCoursesProvider>
                    </ProductSettingsProvider>
                  </Suspense>
                </ConversationProvider>
              </SourceDrawerProvider>
            </NotificationProvider>
          </BackendStatusProvider>
        </AcademicApiProvider>
      </ProductSetupProvider>
      <ServiceWorkerRegister />
      <KeyboardShortcuts />
    </PreferencesProvider>
  );
}
