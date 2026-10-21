"use client";

import Link from "next/link";
import type { WakeWordPhase } from "@/lib/voice/wake-word-state";
import { wakeWordUnsupportedLabel } from "@/lib/voice/wake-word-state";

export function VoiceHandsFreeBar({
  wakeEnabled,
  wakeAvailable,
  wakePhase,
  wakeLabel,
  autoSpeak,
  onToggleWake,
  onToggleAutoSpeak,
  autoSpeakAvailable,
}: {
  wakeEnabled: boolean;
  wakeAvailable: boolean;
  wakePhase: WakeWordPhase;
  wakeLabel: string | null;
  autoSpeak: boolean;
  onToggleWake: () => void;
  onToggleAutoSpeak: () => void;
  autoSpeakAvailable: boolean;
}) {
  const unsupported = wakeWordUnsupportedLabel(wakeAvailable);

  return (
    <div
      className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-xs"
      aria-label="Voice controls"
    >
      <span className="font-medium text-[var(--foreground)]">Voice</span>
      <label className="flex items-center gap-1">
        <input
          type="checkbox"
          checked={wakeEnabled}
          disabled={!wakeAvailable}
          onChange={onToggleWake}
          aria-label='Hands-free "Hey Canvas" wake phrase'
        />
        Hands-free &quot;Hey Canvas&quot;
      </label>
      <label className="flex items-center gap-1">
        <input
          type="checkbox"
          checked={autoSpeak}
          disabled={!autoSpeakAvailable}
          onChange={onToggleAutoSpeak}
          aria-label="Spoken assistant responses"
        />
        Spoken responses
      </label>
      {unsupported ? (
        <span className="text-[var(--warn-text)]" role="status">{unsupported}</span>
      ) : null}
      {wakeEnabled && wakeLabel ? (
        <span
          className={wakePhase === "error" ? "text-[var(--warn-text)]" : "text-[var(--muted)]"}
          role="status"
          aria-live="polite"
        >
          {wakePhase === "error"
            ? "Hands-free voice needs microphone attention; it is not listening."
            : wakeLabel}
        </span>
      ) : null}
      {wakePhase === "error" ? (
        <Link href="/settings#voice" className="underline text-[var(--accent)]">
          Fix microphone
        </Link>
      ) : null}
      <span className="text-[var(--muted)]">
        Push-to-talk mic below. No audio is stored.
      </span>
    </div>
  );
}
