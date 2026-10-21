"use client";

import { useId, useRef } from "react";
import type { VoiceUiPhase } from "@/hooks/useVoiceInput";

export function ChatComposer({
  disabled,
  streaming,
  selectedCourseId = "",
  text,
  onTextChange,
  onSend,
  onCancel,
  voiceAvailable,
  voicePhase,
  voiceError,
  onVoiceToggle,
  onVoiceStop,
  autoSpeakEnabled,
  onAutoSpeakToggle,
  voiceOutputAvailable,
}: {
  disabled?: boolean;
  streaming?: boolean;
  selectedCourseId?: string;
  text: string;
  onTextChange: (value: string) => void;
  onSend: (text: string, courseId?: string) => void;
  onCancel?: () => void;
  voiceAvailable?: boolean;
  voicePhase?: VoiceUiPhase;
  voiceError?: string | null;
  onVoiceToggle?: () => void;
  onVoiceStop?: () => void;
  autoSpeakEnabled?: boolean;
  onAutoSpeakToggle?: () => void;
  voiceOutputAvailable?: boolean;
}) {
  const textareaId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled || streaming) return;
    if (!trimmed.replace(/\s/g, "")) return;
    onSend(trimmed, selectedCourseId || undefined);
    onTextChange("");
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const inputDisabled = disabled || streaming;
  const listening = voicePhase === "listening" || voicePhase === "requesting_permission";
  const voiceStatus = voiceStatusLabel(voicePhase, voiceError);

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-3 shadow-sm">
      {voiceStatus ? (
        <p className="mb-2 text-xs text-[var(--muted)]" role="status" aria-live="polite">
          {voiceStatus}
        </p>
      ) : null}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          id={textareaId}
          rows={2}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={inputDisabled}
          readOnly={listening}
          placeholder="Ask Hey Canvas anything about your academics…"
          className="min-h-[3rem] max-h-40 flex-1 resize-y rounded-xl border border-transparent bg-[var(--surface-muted)] px-3 py-2 text-sm focus-visible:border-[var(--accent)] focus-visible:outline-none"
          aria-label="Message Hey Canvas"
        />
        {voiceOutputAvailable && onAutoSpeakToggle ? (
          <button
            type="button"
            aria-pressed={autoSpeakEnabled}
            aria-label={autoSpeakEnabled ? "Spoken responses on" : "Spoken responses off"}
            onClick={onAutoSpeakToggle}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border text-xs ${
              autoSpeakEnabled
                ? "border-[var(--accent)] text-[var(--accent)]"
                : "border-[var(--border)] text-[var(--muted)]"
            }`}
            title="Toggle spoken assistant summaries"
          >
            🔊
          </button>
        ) : null}
        <button
          type="button"
          aria-label={listening ? "Stop listening" : "Start voice input"}
          aria-pressed={listening}
          disabled={!voiceAvailable || inputDisabled}
          title={!voiceAvailable ? "Voice input is not available in this browser" : undefined}
          onClick={() => {
            if (listening) onVoiceStop?.();
            else onVoiceToggle?.();
          }}
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
            listening
              ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-fg)]"
              : "border-[var(--border)] text-[var(--muted)]"
          } disabled:opacity-50`}
        >
          <MicIcon />
        </button>
        {streaming && onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="h-10 shrink-0 rounded-xl border border-[var(--border)] px-4 text-sm font-medium hover:bg-[var(--surface-muted)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={inputDisabled || !text.trim()}
            className="h-10 shrink-0 rounded-xl bg-[var(--accent)] px-4 text-sm font-medium text-[var(--accent-fg)] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}

function voiceStatusLabel(phase?: VoiceUiPhase, error?: string | null): string | null {
  if (error) return error;
  switch (phase) {
    case "requesting_permission":
      return "Requesting microphone permission…";
    case "listening":
      return "Listening… speak, then tap the mic to finish.";
    case "processing":
      return "Processing speech…";
    case "speaking":
      return "Speaking response…";
    default:
      return null;
  }
}

function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M19 11a7 7 0 0 1-14 0M12 18v3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
