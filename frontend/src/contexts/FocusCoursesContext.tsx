"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import type { Course } from "@/lib/domain/types";
import {
  focusRolloverHint,
  inferDominantTerm,
  resolveFocusCourses,
  suggestInitialFocusCourseIds,
  toggleFocusCourseId,
} from "@/lib/product/focus-courses";
import { readCourseAiPolicies, writeCourseAiPolicies } from "@/lib/product/course-ai-policy";
import { sanitizeFocusAndPoliciesForCatalog } from "@/lib/product/catalog-sanitize";

interface FocusCoursesContextValue {
  catalog: Course[];
  focusCourseIds: string[];
  focusCourses: Course[];
  loading: boolean;
  settingsSource: string | null;
  rolloverHint: string | null;
  setFocusCourseIds: (ids: string[]) => void;
  toggleFocus: (courseId: string) => void;
  suggestInitial: () => string[];
  refresh: () => void;
}

const FocusCoursesContext = createContext<FocusCoursesContextValue | null>(null);

export function FocusCoursesProvider({ children }: { children: React.ReactNode }) {
  const api = useAcademicApi();
  const { settings, setFocusCourseIds: persistFocus, loading: settingsLoading, source } =
    useProductSettings();
  const [catalog, setCatalog] = useState<Course[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);

  const refresh = useCallback(() => {
    setCatalogLoading(true);
    api
      .getCourses()
      .then((courses) => setCatalog(courses))
      .catch(() => setCatalog([]))
      .finally(() => setCatalogLoading(false));
  }, [api]);

  useEffect(() => {
    let active = true;
    api
      .getCourses()
      .then((courses) => {
        if (active) setCatalog(courses);
      })
      .catch(() => {
        if (active) setCatalog([]);
      })
      .finally(() => {
        if (active) setCatalogLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    if (catalogLoading || !settings || catalog.length === 0) return;
    const { focusCourseIds: sanitizedFocus, policies } = sanitizeFocusAndPoliciesForCatalog(
      settings.focusCourseIds,
      catalog,
      readCourseAiPolicies(),
    );
    const currentPolicies = readCourseAiPolicies();
    const policiesPruned =
      Object.keys(currentPolicies).length !== Object.keys(policies).length;
    if (policiesPruned) writeCourseAiPolicies(policies);
    if (sanitizedFocus.length !== settings.focusCourseIds.length) {
      void persistFocus(sanitizedFocus, inferDominantTerm(catalog));
    }
    // Intentionally omit full `settings` object to avoid re-sanitize loops on unrelated fields.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- settings.focusCourseIds + catalog are sufficient
  }, [catalog, catalogLoading, settings?.focusCourseIds, persistFocus]);

  const focusCourseIds = useMemo(
    () => settings?.focusCourseIds ?? [],
    [settings?.focusCourseIds],
  );

  const setFocusCourseIds = useCallback(
    (ids: string[]) => {
      const termHint = inferDominantTerm(catalog);
      void persistFocus(ids, termHint);
    },
    [catalog, persistFocus],
  );

  const toggleFocus = useCallback(
    (courseId: string) => {
      setFocusCourseIds(toggleFocusCourseId(courseId, focusCourseIds));
    },
    [focusCourseIds, setFocusCourseIds],
  );

  const focusCourses = useMemo(
    () => resolveFocusCourses(focusCourseIds, catalog),
    [focusCourseIds, catalog],
  );

  const rolloverHint = useMemo(() => {
    if (!settings) return null;
    return focusRolloverHint(
      {
        version: 1,
        focusCourseIds: settings.focusCourseIds,
        termHint: settings.termHint,
        updatedAt: settings.updatedAt,
      },
      catalog,
    );
  }, [settings, catalog]);

  const value = useMemo(
    () => ({
      catalog,
      focusCourseIds,
      focusCourses,
      loading: catalogLoading || settingsLoading,
      settingsSource: source,
      rolloverHint,
      setFocusCourseIds,
      toggleFocus,
      suggestInitial: () => suggestInitialFocusCourseIds(catalog),
      refresh,
    }),
    [
      catalog,
      focusCourseIds,
      focusCourses,
      catalogLoading,
      settingsLoading,
      source,
      rolloverHint,
      setFocusCourseIds,
      toggleFocus,
      refresh,
    ],
  );

  return (
    <FocusCoursesContext.Provider value={value}>{children}</FocusCoursesContext.Provider>
  );
}

export function useFocusCourses(): FocusCoursesContextValue {
  const ctx = useContext(FocusCoursesContext);
  if (!ctx) throw new Error("useFocusCourses requires FocusCoursesProvider");
  return ctx;
}
