"use client";

import { useCallback, useRef } from "react";
import { isSpeechSynthesisAvailable, speakText, stopSpeaking } from "@/lib/voice/speech-synthesis";
import type { ChatMessage } from "@/lib/domain/types";
import { summarizeMessageForSpeech } from "@/lib/voice/spoken-summary";

export function useVoiceOutput() {
  const lastSpokenRef = useRef<string | null>(null);

  const speakMessage = useCallback((message: ChatMessage, onEnd?: () => void) => {
    if (!isSpeechSynthesisAvailable()) return;
    const summary = summarizeMessageForSpeech(message);
    if (!summary.trim()) return;
    lastSpokenRef.current = summary;
    speakText(summary, { onEnd });
  }, []);

  const cancelSpeech = useCallback(() => {
    stopSpeaking();
    lastSpokenRef.current = null;
  }, []);

  return {
    available: isSpeechSynthesisAvailable(),
    speakMessage,
    cancelSpeech,
    lastSpokenRef,
  };
}
