"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NAV_ITEMS } from "@/components/layout/nav";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useCourseContext } from "@/contexts/CourseContext";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { buildStudyWorkspaceUrl } from "@/lib/navigation/study-links";
import type { Assignment, Course, DocumentSearchResult } from "@/lib/domain/types";

type CommandItem = {
  id: string;
  label: string;
  hint?: string;
  href: string;
  group: string;
};

export function CommandPalette() {
  const api = useAcademicApi();
  const { courseId } = useCourseContext();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [entities, setEntities] = useState<{
    courses: Course[];
    assignments: Assignment[];
    materials: DocumentSearchResult[];
  }>({ courses: [], assignments: [], materials: [] });
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    Promise.all([
      api.getCourses(),
      api.getAssignments(),
      api.searchDocuments({ query: "" }).catch(() => [] as DocumentSearchResult[]),
    ]).then(([courses, assignments, materials]) => {
      setEntities({ courses, assignments, materials });
    });
  }, [api, open]);

  const items = useMemo(() => {
    const nav: CommandItem[] = [
      ...NAV_ITEMS.map((n) => ({
        id: `nav-${n.href}`,
        label: n.label,
        href: n.href,
        group: "Navigate",
      })),
      { id: "nav-dashboard", label: "Dashboard", href: "/dashboard", group: "Navigate" },
      { id: "nav-workload", label: "Workload", href: "/workload", group: "Navigate" },
      { id: "nav-sync", label: "Sync history", href: "/sync", group: "Navigate" },
      { id: "nav-settings", label: "Settings", href: "/settings", group: "Navigate" },
      {
        id: "hey-today",
        label: "Hey Canvas: What's due today?",
        href: buildHeyCanvasUrl({ prompt: "What's due today?" }),
        group: "Hey Canvas",
      },
      {
        id: "hey-week",
        label: "Hey Canvas: Plan my week",
        href: buildHeyCanvasUrl({ prompt: "What should I work on this week?" }),
        group: "Hey Canvas",
      },
      {
        id: "hey-open",
        label: "Open Hey Canvas",
        href: buildHeyCanvasUrl(),
        group: "Hey Canvas",
      },
      {
        id: "nav-changes",
        label: "Review changes",
        href: "/changes",
        group: "Navigate",
      },
      {
        id: "nav-study",
        label: "Study session",
        href: "/study",
        group: "Navigate",
      },
      {
        id: "nav-study-guide",
        label: "Study guide",
        href: "/study/guide",
        group: "Navigate",
      },
      {
        id: "nav-notifications",
        label: "Notifications",
        href: "/notifications",
        group: "Navigate",
      },
      {
        id: "continue-study",
        label: "Continue studying",
        href: buildStudyWorkspaceUrl({ courseId: courseId ?? undefined, continueSession: true }),
        group: "Study",
      },
      ...(courseId
        ? [
            {
              id: "study-current-course",
              label: "Study current course",
              href: buildStudyWorkspaceUrl({ courseId }),
              group: "Study",
            },
          ]
        : []),
    ];
    const courseItems = entities.courses.flatMap((c) => [
      {
        id: `course-${c.id}`,
        label: c.name,
        hint: c.code,
        href: `/courses/${c.id}`,
        group: "Courses",
      },
      {
        id: `hey-course-${c.id}`,
        label: `Ask Hey Canvas about ${c.name}`,
        hint: "Hey Canvas",
        href: buildHeyCanvasUrl({ courseId: c.id, prompt: `What should I focus on in ${c.name}?` }),
        group: "Hey Canvas",
      },
    ]);
    const assignmentItems = entities.assignments.map((a) => ({
      id: `asgn-${a.id}`,
      label: a.title,
      hint: "Assignment",
      href: `/assignments/${a.id}`,
      group: "Assignments",
    }));
    const materialItems = entities.materials.map((m) => ({
      id: `doc-${m.documentId}`,
      label: m.title,
      hint: m.courseName,
      href: `/materials/${m.documentId}`,
      group: "Materials",
    }));
    const all = [...nav, ...courseItems, ...assignmentItems, ...materialItems];
    const q = query.trim().toLowerCase();
    if (!q) return all.slice(0, 40);
    return all
      .filter(
        (item) =>
          item.label.toLowerCase().includes(q) ||
          item.hint?.toLowerCase().includes(q) ||
          item.group.toLowerCase().includes(q),
      )
      .slice(0, 40);
  }, [entities, query, courseId]);

  const select = useCallback(
    (item: CommandItem) => {
      setOpen(false);
      setQuery("");
      router.push(item.href);
    },
    [router],
  );

  const safeActive = Math.min(active, Math.max(0, items.length - 1));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (!open) return;
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((i) => Math.min(i + 1, items.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((i) => Math.max(i - 1, 0));
      }
      if (e.key === "Enter" && items[safeActive]) {
        e.preventDefault();
        select(items[safeActive]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, items, active, safeActive, select]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-50 bg-black/40"
        aria-label="Close command palette"
        onClick={() => setOpen(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="fixed left-1/2 top-[12%] z-50 w-[min(100%-2rem,32rem)] -translate-x-1/2 rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl"
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          placeholder="Search navigation, courses, assignments, materials…"
          className="w-full border-b border-[var(--border)] px-4 py-3 text-sm focus:outline-none"
          aria-controls="command-palette-list"
          aria-activedescendant={items[safeActive] ? `cmd-${items[safeActive].id}` : undefined}
        />
        <ul id="command-palette-list" className="max-h-80 overflow-y-auto py-2" role="listbox">
          {items.length === 0 ? (
            <li className="px-4 py-3 text-sm text-[var(--muted)]">No matches</li>
          ) : (
            items.map((item, index) => (
              <li key={item.id} role="option" aria-selected={index === safeActive} id={`cmd-${item.id}`}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(index)}
                  onClick={() => select(item)}
                  className={`flex w-full items-center justify-between px-4 py-2 text-left text-sm ${
                    index === safeActive ? "bg-[var(--surface-muted)]" : ""
                  }`}
                >
                  <span className="truncate font-medium">{item.label}</span>
                  <span className="ml-2 shrink-0 text-xs text-[var(--muted)]">
                    {item.hint ?? item.group}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
          ↑↓ navigate · Enter select · Esc close
        </p>
      </div>
    </>
  );
}

export function CommandPaletteTrigger() {
  return (
    <button
      type="button"
      className="hidden rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] md:inline"
      onClick={() => {
        window.dispatchEvent(
          new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }),
        );
      }}
    >
      Ctrl+K
    </button>
  );
}
