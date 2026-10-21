"use client";

import { useEffect, useState } from "react";

export function KeyboardShortcuts() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const target = e.target as HTMLElement | null;
        if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
      if (e.key === "/" && !e.metaKey && !e.ctrlKey) {
        const target = e.target as HTMLElement | null;
        if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;
        if (window.location.pathname === "/" || window.location.pathname === "") {
          e.preventDefault();
          const composer = document.querySelector<HTMLTextAreaElement>(
            'textarea[aria-label="Message Hey Canvas"]',
          );
          composer?.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-50 bg-black/40"
        aria-label="Close keyboard shortcuts"
        onClick={() => setOpen(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="keyboard-shortcuts-title"
        className="fixed left-1/2 top-[15%] z-50 w-[min(100%-2rem,24rem)] -translate-x-1/2 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl"
      >
        <h2 id="keyboard-shortcuts-title" className="text-sm font-semibold">Keyboard shortcuts</h2>
        <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
          <li><kbd className="rounded border px-1">Ctrl</kbd>+<kbd className="rounded border px-1">K</kbd> Command palette</li>
          <li><kbd className="rounded border px-1">/</kbd> Focus Hey Canvas composer (home)</li>
          <li><kbd className="rounded border px-1">?</kbd> This help</li>
          <li><kbd className="rounded border px-1">Esc</kbd> Close dialogs / stop overlays</li>
        </ul>
      </div>
    </>
  );
}
