import { CommandPalette } from "@/components/command-palette/CommandPalette";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { MobileNav } from "@/components/layout/MobileNav";
import { TopBar } from "@/components/layout/TopBar";
import { OnboardingGate } from "@/components/product/OnboardingGate";
import { OfflineFreshnessBanner } from "@/components/product/OfflineFreshnessBanner";
import { StartupGuidanceBanner } from "@/components/product/StartupGuidanceBanner";
import { AppMain } from "@/components/layout/AppMain";
import { SourceDrawer } from "@/components/sources/SourceDrawer";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <OnboardingGate>
      <div className="flex h-dvh min-h-0 w-full overflow-hidden">
        <AppSidebar />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <OfflineFreshnessBanner />
          <StartupGuidanceBanner />
          <MobileNav />
          <TopBar />
          <AppMain>{children}</AppMain>
        </div>
        <SourceDrawer />
        <CommandPalette />
      </div>
    </OnboardingGate>
  );
}
