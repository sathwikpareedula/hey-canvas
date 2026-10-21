"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { CourseNavSection } from "@/components/layout/CourseNavSection";
import { NAV_ITEMS } from "@/components/layout/nav";
import { SyncStatus } from "@/components/sync/SyncStatus";

const SIDEBAR_COLLAPSED_KEY = "hey_canvas_sidebar_collapsed";

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
        if (stored === "true") {
          queueMicrotask(() => setCollapsed(true));
        }
      } catch {}
    }
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
        } catch {}
      }
      return next;
    });
  };

  return (
    <aside
      className={`hidden h-full min-h-0 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] transition-all duration-200 md:flex ${
        collapsed ? "w-16" : "w-60 max-w-[min(100vw,15rem)]"
      }`}
      aria-label="Primary"
    >
      <div className={`flex items-center px-3 py-5 ${collapsed ? "justify-center" : "justify-between"}`}>
        <Link
          href="/"
          className="flex items-center gap-3 rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          title="Hey Canvas Home"
        >
          <span
            aria-hidden="true"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--surface-muted)] text-xl font-semibold text-[var(--accent)] shadow-xs transition hover:scale-105"
          >
            ✦
          </span>
          {!collapsed && (
            <span className="min-w-0">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--muted)]">
                ACADEMIC SPACE
              </span>
              <span className="block text-base font-bold tracking-tight text-[var(--foreground)]">
                Hey Canvas
              </span>
            </span>
          )}
        </Link>
        <button
          type="button"
          onClick={toggleCollapsed}
          className="rounded-lg p-1.5 text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)] transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-2" aria-label="Workspace sections">
        {!collapsed && (
          <p className="px-3 pb-1.5 text-[10px] font-bold uppercase tracking-[.18em] text-[var(--muted)]">
            Workspace
          </p>
        )}
        {NAV_ITEMS.slice(0, 4).map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
                active
                  ? "bg-[var(--surface-muted)] font-semibold text-[var(--foreground)]"
                  : "text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]"
              } ${collapsed ? "justify-center" : ""}`}
              aria-current={active ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <span className="text-base select-none">
                {item.href === "/" ? "💬" : item.href.includes("workspace") ? "📚" : item.href.includes("deadlines") ? "📅" : "📝"}
              </span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}

        {!collapsed && (
          <div className="my-2 border-t border-[var(--border)] pt-2">
            <CourseNavSection />
          </div>
        )}

        {NAV_ITEMS.slice(4).map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
                active
                  ? "bg-[var(--surface-muted)] font-semibold text-[var(--foreground)]"
                  : "text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]"
              } ${collapsed ? "justify-center" : ""}`}
              aria-current={active ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <span className="text-base select-none">
                {item.href.includes("materials") ? "📂" : item.href.includes("planning") ? "⏱️" : "📊"}
              </span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className={`space-y-2 border-t border-[var(--border)] p-2 ${collapsed ? "text-center" : ""}`}>
        {!collapsed && (
          <>
            <p className="px-3 text-[10px] font-bold uppercase tracking-[.18em] text-[var(--muted)]">
              Status & preferences
            </p>
            <SyncStatus variant="sidebar" />
          </>
        )}
        <Link
          href="/settings"
          className={`flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)] transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
            collapsed ? "justify-center" : ""
          }`}
          title={collapsed ? "Settings" : undefined}
        >
          <span className="text-base select-none">⚙️</span>
          {!collapsed && <span>Settings</span>}
        </Link>
      </div>
    </aside>
  );
}
