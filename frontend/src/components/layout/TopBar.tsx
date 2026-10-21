"use client";

import { usePathname } from "next/navigation";
import { CommandPaletteTrigger } from "@/components/command-palette/CommandPalette";
import { PAGE_TITLES } from "@/components/layout/nav";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { BackendStatusBadge } from "@/components/status/BackendStatusBadge";
import { DemoDataBadge } from "@/components/status/DemoDataBadge";
import { SyncStatus } from "@/components/sync/SyncStatus";
import { useDemoDataBadge } from "@/hooks/useDemoDataBadge";

function titleForPath(pathname: string): string {
  if (pathname.startsWith("/courses/") && pathname !== "/courses") {
    return "Course workspace";
  }
  if (pathname.startsWith("/assignments/")) return "Assignment";
  if (pathname.startsWith("/materials/") && pathname !== "/materials") return "Material";
  return PAGE_TITLES[pathname] ?? "Hey Canvas";
}

export function TopBar() {
  const pathname = usePathname();
  const showDemoBadge = useDemoDataBadge();
  return (
    <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)]/80 px-4 py-3 backdrop-blur-sm md:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <h1 className="text-base font-semibold tracking-tight truncate">{titleForPath(pathname)}</h1>
        {showDemoBadge ? <DemoDataBadge /> : null}
      </div>
      <div className="flex items-center gap-2">
        <BackendStatusBadge compact />
        <CommandPaletteTrigger />
        <NotificationBell />
        <div className="hidden sm:block max-w-xs">
          <SyncStatus variant="inline" />
        </div>
      </div>
    </header>
  );
}
