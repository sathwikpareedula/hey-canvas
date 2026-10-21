"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useMemo } from "react";

interface CourseContextValue {
  courseId: string | null;
  setCourseId: (id: string | null) => void;
  clearCourseId: () => void;
}

export function buildCourseContextUrl(
  pathname: string | null | undefined,
  search: URLSearchParams | { toString(): string } | string | null | undefined,
  courseId: string | null,
): string {
  const currentPath = pathname && pathname.length > 0 ? pathname : "/";
  const params = new URLSearchParams(typeof search === "string" ? search : search?.toString() ?? "");

  if (courseId) params.set("courseId", courseId);
  else params.delete("courseId");

  const qs = params.toString();
  return qs ? `${currentPath}?${qs}` : currentPath;
}

const CourseContext = createContext<CourseContextValue | null>(null);

function useCourseIdFromUrl(): string | null {
  const search = useSearchParams();
  return search.get("courseId");
}

export function CourseContextProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const courseId = useCourseIdFromUrl();

  const setCourseId = useCallback(
    (id: string | null) => {
      router.push(buildCourseContextUrl(pathname, search, id));
    },
    [pathname, router, search],
  );

  const value = useMemo(
    () => ({
      courseId,
      setCourseId,
      clearCourseId: () => setCourseId(null),
    }),
    [courseId, setCourseId],
  );

  return <CourseContext.Provider value={value}>{children}</CourseContext.Provider>;
}

export function useCourseContext() {
  const ctx = useContext(CourseContext);
  if (!ctx) throw new Error("useCourseContext must be used within CourseContextProvider");
  return ctx;
}

/** Optional hook for components outside URL-driven hey canvas routes. */
export function useOptionalCourseContext() {
  return useContext(CourseContext);
}
