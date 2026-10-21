"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { CourseNavSection } from "@/components/layout/CourseNavSection";
import { NAV_ITEMS } from "@/components/layout/nav";
import { SyncStatus } from "@/components/sync/SyncStatus";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="border-b border-[var(--border)] bg-[var(--surface)] md:hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <Link href="/" className="text-base font-semibold">Hey Canvas</Link>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          aria-expanded={open}
          aria-controls="mobile-nav-drawer"
        >
          Menu
        </button>
      </div>
      {open ? (
        <nav id="mobile-nav-drawer" className="border-t border-[var(--border)] px-2 pb-3">
          {NAV_ITEMS.slice(0, 3).map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`block rounded-lg px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
                  active ? "bg-[var(--surface-muted)] font-medium" : "text-[var(--muted)]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <CourseNavSection />
          {NAV_ITEMS.slice(3).map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`block rounded-lg px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
                  active ? "bg-[var(--surface-muted)] font-medium" : "text-[var(--muted)]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <div className="mt-2 px-1">
            <SyncStatus variant="inline" />
          </div>
          <Link
            href="/settings"
            onClick={() => setOpen(false)}
            className="mt-1 block rounded-lg px-3 py-2 text-sm text-[var(--muted)]"
          >
            Settings
          </Link>
        </nav>
      ) : null}
    </div>
  );
}
