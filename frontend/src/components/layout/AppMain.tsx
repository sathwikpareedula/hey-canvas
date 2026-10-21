"use client";

import { usePathname } from "next/navigation";

/** Home chat owns internal scroll; other routes scroll the main column. */
export function AppMain({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const chatHome = pathname === "/";
  return (
    <main
      className={`flex min-h-0 flex-1 flex-col px-4 py-6 md:px-8 ${
        chatHome ? "overflow-hidden" : "overflow-y-auto"
      }`}
    >
      {children}
    </main>
  );
}
