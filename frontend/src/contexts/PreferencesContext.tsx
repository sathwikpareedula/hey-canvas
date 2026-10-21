"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type ThemePreference = "light" | "dark" | "system";
export type Density = "comfortable" | "compact";
export type LandingPage =
  | "/"
  | "/dashboard"
  | "/today"
  | "/courses"
  | "/assignments"
  | "/materials";

interface Preferences {
  theme: ThemePreference;
  density: Density;
  landingPage: LandingPage;
  displayName: string;
}

interface PreferencesContextValue extends Preferences {
  setTheme: (t: ThemePreference) => void;
  setDensity: (d: Density) => void;
  setLandingPage: (p: LandingPage) => void;
  resolvedTheme: "light" | "dark";
}

const STORAGE_KEY = "hey-canvas-preferences";

const defaultPrefs: Preferences = {
  theme: "system",
  density: "comfortable",
  landingPage: "/",
  displayName: "Student",
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function loadPrefs(): Preferences {
  if (typeof window === "undefined") return defaultPrefs;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultPrefs;
    return { ...defaultPrefs, ...JSON.parse(raw) };
  } catch {
    return defaultPrefs;
  }
}

function applyDocumentPrefs(resolved: "light" | "dark", density: Density) {
  document.documentElement.classList.toggle("dark", resolved === "dark");
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.density = density;
}

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);

  useEffect(() => {
    const stored = loadPrefs();
    queueMicrotask(() => setPrefs(stored));
  }, []);

  const resolvedTheme = useMemo((): "light" | "dark" => {
    if (prefs.theme === "light") return "light";
    if (prefs.theme === "dark") return "dark";
    if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }, [prefs.theme]);

  useEffect(() => {
    applyDocumentPrefs(resolvedTheme, prefs.density);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (prefs.theme === "system") {
        applyDocumentPrefs(mq.matches ? "dark" : "light", prefs.density);
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [prefs.theme, prefs.density, resolvedTheme]);

  const persist = useCallback((next: Preferences) => {
    setPrefs(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const value = useMemo<PreferencesContextValue>(
    () => ({
      ...prefs,
      resolvedTheme,
      setTheme: (theme) => persist({ ...prefs, theme }),
      setDensity: (density) => persist({ ...prefs, density }),
      setLandingPage: (landingPage) => persist({ ...prefs, landingPage }),
    }),
    [prefs, persist, resolvedTheme],
  );

  return (
    <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error("usePreferences must be used within PreferencesProvider");
  return ctx;
}
