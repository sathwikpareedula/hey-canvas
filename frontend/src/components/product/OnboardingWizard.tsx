"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { FocusCoursePicker } from "@/components/product/FocusCoursePicker";
import { SyncStatus } from "@/components/sync/SyncStatus";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { useFocusCourses } from "@/contexts/FocusCoursesContext";
import { useProductSettings } from "@/contexts/ProductSettingsContext";
import { useProductSetup } from "@/contexts/ProductSetupContext";
import { ReadinessPanel } from "@/components/product/ReadinessPanel";
import { LocalAiSettingsPanel } from "@/components/settings/LocalAiSettingsPanel";
import { CanvasConnectionGuide } from "@/components/product/CanvasConnectionGuide";
import { SemesterRolloverBanner } from "@/components/product/SemesterRolloverBanner";
import {
  canSkipFocusCourseStep,
  onboardingResumeTarget,
  onboardingStepLabel,
} from "@/lib/product/onboarding";
import { useDemoDataBadge } from "@/hooks/useDemoDataBadge";

function StepNav({
  onBack,
  onNext,
  nextLabel = "Continue",
  nextDisabled,
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
}) {
  return (
    <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Back
        </button>
      ) : (
        <span />
      )}
      <button
        type="button"
        disabled={nextDisabled}
        onClick={onNext}
        className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
      >
        {nextLabel}
      </button>
    </div>
  );
}

export function OnboardingWizard() {
  const router = useRouter();
  const { onboarding, nextStep, prevStep, completeSetup, goToStep } = useProductSetup();
  const { settings, updateAi } = useProductSettings();
  const aiPreferences = settings
    ? { processingMode: settings.aiProcessingMode, localModelTier: settings.localModelTier }
    : { processingMode: "local" as const, localModelTier: "recommended" as const };
  const { mode, connection } = useBackendStatus();
  const { catalog, focusCourseIds, setFocusCourseIds, suggestInitial, loading } = useFocusCourses();
  const isDemo = useDemoDataBadge();
  const step = onboarding.currentStep;
  useEffect(() => {
    if (step === "focus" && focusCourseIds.length === 0 && catalog.length > 0) {
      setFocusCourseIds(suggestInitial());
    }
  }, [step, focusCourseIds.length, catalog.length, setFocusCourseIds, suggestInitial]);

  const finish = () => {
    completeSetup();
    router.replace("/dashboard");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 pb-12">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-widest text-[var(--muted)]">
          Setup · {onboardingStepLabel(step)}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome to Hey Canvas</h1>
        <p className="text-sm text-[var(--muted)]">
          ChatGPT for your semester — it already knows your authorized Canvas courses, assignments,
          and materials. No uploads required for ordinary questions.
        </p>
      </header>

      {step === "welcome" && (
        <section className="space-y-4 rounded-xl border border-[var(--border)] p-5">
          <p className="text-sm">
            Four quick steps: check Canvas and sync status, choose focus courses for your sidebar,
            pick local AI on this computer, then start chatting. Your academic data stays on this
            device by default.
          </p>
          {isDemo ? (
            <p className="rounded-lg bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--muted)]">
              Demo mode uses synthetic sample data only — safe for screenshots and portfolio viewers.
            </p>
          ) : null}
          <StepNav onNext={nextStep} nextLabel="Get started" />
          <button
            type="button"
            className="text-xs text-[var(--muted)] underline"
            onClick={() => goToStep(onboardingResumeTarget(onboarding))}
          >
            Resume where I left off
          </button>
        </section>
      )}

      {step === "sync" && (
        <section className="space-y-4 rounded-xl border border-[var(--border)] p-5">
          <h2 className="text-sm font-semibold">Canvas and local data</h2>
          <p className="text-sm text-[var(--muted)]">
            Hey Canvas uses read-only Canvas access through the service on your computer (not your
            browser password). Course data syncs locally so answers stay fast and private.
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
            <li>No automatic submissions or grade changes</li>
            <li>You can use synced data even when live Canvas is unavailable</li>
          </ul>
          <CanvasConnectionGuide />
          <SyncStatus variant="inline" />
          <ReadinessPanel compact />
          {mode === "mock" ? (
            <p className="text-xs text-[var(--muted)]">Demo catalog is already loaded.</p>
          ) : connection !== "connected" ? (
            <p className="text-xs text-[var(--warn-text)]">
              Local service not connected. You can continue setup and sync later from Settings.
            </p>
          ) : null}
          <StepNav onBack={prevStep} onNext={nextStep} />
        </section>
      )}

      {step === "focus" && (
        <section className="space-y-4 rounded-xl border border-[var(--border)] p-5">
          <h2 className="text-sm font-semibold">Choose focus courses</h2>
          <p className="text-sm text-[var(--muted)]">
            Focus courses appear in your sidebar and daily views. You can change them anytime. All
            courses remain available under All courses.
          </p>
          <SemesterRolloverBanner />
          {loading ? (
            <p className="text-sm text-[var(--muted)]" role="status">Loading course list…</p>
          ) : (
            <FocusCoursePicker
              catalog={catalog}
              selectedIds={focusCourseIds}
              onChange={setFocusCourseIds}
            />
          )}
          <StepNav
            onBack={prevStep}
            onNext={nextStep}
            nextDisabled={!loading && catalog.length > 0 && focusCourseIds.length === 0}
          />
          {!loading && canSkipFocusCourseStep(catalog.length) ? (
            <button
              type="button"
              className="text-xs text-[var(--muted)] underline"
              onClick={nextStep}
            >
              Skip for now — no courses synced yet
            </button>
          ) : null}
        </section>
      )}

      {step === "local_ai" && (
        <section className="space-y-4 rounded-xl border border-[var(--border)] p-5">
          <h2 className="text-sm font-semibold">Local AI</h2>
          <p className="text-sm text-[var(--muted)]">
            Hey Canvas answers from your synced courses using a model on this computer — fast,
            private, and free. Pick an installed Ollama model you already have; nothing is downloaded
            automatically here.
          </p>
          <LocalAiSettingsPanel compact />
          <StepNav onBack={prevStep} onNext={nextStep} />
        </section>
      )}

      {step === "privacy" && (
        <section className="space-y-4 rounded-xl border border-[var(--border)] p-5">
          <h2 className="text-sm font-semibold">Privacy in plain language</h2>
          <ul className="space-y-2 text-sm text-[var(--muted)]">
            <li>Canvas access is read-only.</li>
            <li>Synced academic data stays on your computer by default.</li>
            <li>Local models run locally — course content is not sent to OpenAI unless you opt in.</li>
            <li>Cloud mode sends only relevant context you choose to enable.</li>
            <li>Passwords and Canvas tokens are never sent to the model.</li>
          </ul>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={aiPreferences.processingMode === "local"}
              onChange={() => void updateAi({ aiProcessingMode: "local", privacyCloudOptInAcknowledged: true })}
            />
            <span>Keep processing on local AI (recommended)</span>
          </label>
          <StepNav onBack={prevStep} onNext={nextStep} />
        </section>
      )}

      {step === "ready" && (
        <section className="space-y-4 rounded-xl border border-[var(--border)] p-5">
          <h2 className="text-sm font-semibold">You are ready</h2>
          <p className="text-sm text-[var(--muted)]">
            Open a focus course workspace or ask Hey Canvas what is due today. Deterministic deadline
            questions answer instantly from your synced index.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/"
              className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)]"
            >
              Open Hey Canvas
            </Link>
            <Link
              href="/dashboard"
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            >
              Dashboard
            </Link>
          </div>
          <StepNav onBack={prevStep} onNext={finish} nextLabel="Finish setup" />
        </section>
      )}
    </div>
  );
}
