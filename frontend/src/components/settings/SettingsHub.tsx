"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { DataManagementPanel } from "@/components/product/DataManagementPanel";
import { FocusCoursePicker } from "@/components/product/FocusCoursePicker";
import { ReadinessPanel } from "@/components/product/ReadinessPanel";
import { ReminderSettingsPanel } from "@/components/planning/ReminderSettingsPanel";
import { BackendStatusBadge } from "@/components/status/BackendStatusBadge";
import { CanvasConnectionGuide } from "@/components/product/CanvasConnectionGuide";
import { SemesterRolloverBanner } from "@/components/product/SemesterRolloverBanner";
import { SyncStatus } from "@/components/sync/SyncStatus";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { useFocusCourses } from "@/contexts/FocusCoursesContext";
import { usePreferences } from "@/contexts/PreferencesContext";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import { useProductSetup } from "@/contexts/ProductSetupContext";
import { syncCoursePolicyToServer } from "@/lib/api/product-settings-service";
import { getProductSettingsApi } from "@/lib/api/product-settings-service";
import type { Density, LandingPage, ThemePreference } from "@/contexts/PreferencesContext";
import { STUDY_MODE_OPTIONS } from "@/lib/domain/study-mode";
import { LocalAiSettingsPanel } from "@/components/settings/LocalAiSettingsPanel";
import { VoiceSettingsPanel } from "@/components/settings/VoiceSettingsPanel";
import { SecurityHealthCenter } from "@/components/settings/SecurityHealthCenter";
import { StorageSettingsPanel } from "@/components/settings/StorageSettingsPanel";
import {
  AI_POLICY_DISCLAIMER,
  getCourseAiPolicy,
  instructorAiPolicyLabel,
  saveCourseAiPolicy,
  type InstructorAiPolicy,
} from "@/lib/product/course-ai-policy";
import { courseNavLabel } from "@/lib/product/course-display-name";
import { resumeOnboardingAt } from "@/lib/product/onboarding";

const SECTION_CLASS = "space-y-3 rounded-xl border border-[var(--border)] p-4 scroll-mt-20";

export function SettingsHub() {
  const router = useRouter();
  const { theme, density, landingPage, setTheme, setDensity, setLandingPage } = usePreferences();
  const { mode, refresh, checking } = useBackendStatus();
  const { reload } = useProductSetup();
  const { source } = useProductSettings();
  const { catalog, focusCourseIds, setFocusCourseIds, loading, settingsSource } = useFocusCourses();
  const productApi = getProductSettingsApi();
  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <p className="text-sm text-[var(--muted)]">
        Organize Canvas, focus courses, local AI, privacy, and notifications without developer jargon.
      </p>

      <section id="connection" className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Canvas &amp; connection</h2>
        <BackendStatusBadge />
        <SyncStatus variant="inline" />
        <ReadinessPanel />
        <p className="text-xs text-[var(--muted)]">
          Product settings source:{" "}
          <span className="font-medium text-[var(--foreground)]">{source ?? settingsSource ?? "…"}</span>
        </p>
        <CanvasConnectionGuide compact />
        <p className="text-xs text-[var(--muted)]">
          Active data mode: <span className="font-medium text-[var(--foreground)]">{mode}</span>.
        </p>
        <button
          type="button"
          onClick={refresh}
          disabled={checking}
          className="min-h-10 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {checking ? "Checking…" : "Check connection"}
        </button>
      </section>

      <section id="focus-courses" className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Focus courses</h2>
        <p className="text-xs text-[var(--muted)]">
          Focus courses power sidebar navigation and daily prioritization. All synced courses remain
          under{" "}
          <Link href="/courses" className="underline">All courses</Link>.
        </p>
        <SemesterRolloverBanner />
        {loading ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : (
          <FocusCoursePicker
            catalog={catalog}
            selectedIds={focusCourseIds}
            onChange={setFocusCourseIds}
          />
        )}
      </section>

      <section id="local-ai" className={SECTION_CLASS}>
        <LocalAiSettingsPanel />
      </section>

      <section id="security-health" className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Security &amp; Health</h2>
        <SecurityHealthCenter />
      </section>

      <section id="privacy" className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Privacy</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
          <li>Read-only Canvas access.</li>
          <li>Synced data stored locally on your computer.</li>
          <li>Local models run on this device.</li>
          <li>Only relevant context is sent when cloud mode is enabled.</li>
          <li>No credentials are sent to models.</li>
        </ul>
        <p className="text-xs text-[var(--muted)]">
          This UI stores preferences and session ids only — not document bodies or tokens.
        </p>
      </section>

      <section id="course-policies" className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Course AI policy (your notes)</h2>
        <p className="text-xs text-[var(--muted)]">{AI_POLICY_DISCLAIMER}</p>
        {focusCourseIds.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Add focus courses to manage per-course notes.</p>
        ) : (
          <ul className="space-y-4">
            {focusCourseIds.map((id) => {
              const course = catalog.find((c) => c.id === id);
              if (!course) return null;
              const policy = getCourseAiPolicy(id);
              return (
                <li key={id} className="rounded-lg border border-[var(--border)] p-3">
                  <p className="text-sm font-medium">{courseNavLabel(course)}</p>
                  <label className="mt-2 block text-xs">
                    Instructor AI policy (your record)
                    <select
                      className="mt-1 w-full rounded-md border border-[var(--border)] px-2 py-1"
                      value={policy.instructorPolicy}
                      onChange={(e) => {
                        const record = saveCourseAiPolicy(id, {
                          instructorPolicy: e.target.value as InstructorAiPolicy,
                        });
                        void syncCoursePolicyToServer(productApi, id, record);
                      }}
                    >
                      {(["unknown", "allowed", "restricted", "disabled"] as const).map((p) => (
                        <option key={p} value={p}>{instructorAiPolicyLabel(p)}</option>
                      ))}
                    </select>
                  </label>
                  <label className="mt-2 block text-xs">
                    Cloud processing
                    <select
                      className="mt-1 w-full rounded-md border border-[var(--border)] px-2 py-1"
                      value={policy.cloudProcessing}
                      onChange={(e) => {
                        const record = saveCourseAiPolicy(id, {
                          cloudProcessing: e.target.value as "allowed" | "local_only",
                        });
                        void syncCoursePolicyToServer(productApi, id, record);
                      }}
                    >
                      <option value="local_only">Local only</option>
                      <option value="allowed">Allowed (if you enable cloud)</option>
                    </select>
                  </label>
                  <label className="mt-2 block text-xs">
                    Notes
                    <textarea
                      className="mt-1 w-full rounded-md border border-[var(--border)] px-2 py-1"
                      rows={2}
                      value={policy.notes}
                      onChange={(e) => {
                        const record = saveCourseAiPolicy(id, { notes: e.target.value });
                        void syncCoursePolicyToServer(productApi, id, record);
                      }}
                    />
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section id="storage" className={SECTION_CLASS}>
        <StorageSettingsPanel />
      </section>

      <DataManagementPanel />

      <ReminderSettingsPanel />

      <section id="voice" className={SECTION_CLASS}>
        <VoiceSettingsPanel />
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Study modes</h2>
        <p className="text-xs text-[var(--muted)]">
          Study modes are set from the Hey Canvas chat header.
        </p>
        <ul className="space-y-2 text-sm">
          {STUDY_MODE_OPTIONS.map((m) => (
            <li key={m.id} className="rounded-lg bg-[var(--surface-muted)] px-3 py-2">
              <span className="font-medium">{m.label}</span>
              <span className="mt-0.5 block text-xs text-[var(--muted)]">{m.description}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Appearance &amp; navigation</h2>
        <label className="block text-sm">
          Theme
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as ThemePreference)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2"
          >
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
        <label className="block text-sm">
          Density
          <select
            value={density}
            onChange={(e) => setDensity(e.target.value as Density)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2"
          >
            <option value="comfortable">Comfortable</option>
            <option value="compact">Compact</option>
          </select>
        </label>
        <label className="block text-sm">
          Default landing page
          <select
            value={landingPage}
            onChange={(e) => setLandingPage(e.target.value as LandingPage)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2"
          >
            <option value="/dashboard">Dashboard</option>
            <option value="/">Hey Canvas</option>
            <option value="/today">Today</option>
            <option value="/courses">All courses</option>
            <option value="/assignments">Assignments</option>
            <option value="/materials">Materials</option>
          </select>
        </label>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-sm font-semibold">Setup</h2>
        <button
          type="button"
          className="text-sm text-[var(--accent)] underline"
          onClick={() => {
            resumeOnboardingAt("welcome");
            reload();
            router.push("/onboarding");
          }}
        >
          Run setup wizard again
        </button>
      </section>
    </div>
  );
}
