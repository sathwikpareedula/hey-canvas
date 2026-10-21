"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSpeechRecognition,
  isSpeechRecognitionAvailable,
} from "@/lib/voice/speech-recognition";

export type VoiceUiPhase =
  | "idle"
  | "requesting_permission"
  | "listening"
  | "processing"
  | "speaking"
  | "error";

export function useVoiceInput(options?: {
  onFinalTranscript?: (text: string) => void;
}) {
  const [available] = useState(() => isSpeechRecognitionAvailable());
  const [phase, setPhase] = useState<VoiceUiPhase>("idle");
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const engineRef = useRef<ReturnType<typeof createSpeechRecognition>>(null);

  const resetTranscript = useCallback(() => {
    setTranscript("");
    setInterim("");
  }, []);

  const cancel = useCallback(() => {
    engineRef.current?.cancel();
    engineRef.current = null;
    setPhase("idle");
    setInterim("");
  }, []);

  const startListening = useCallback(() => {
    if (!available) {
      setError("Speech recognition is not supported in this browser.");
      setPhase("error");
      return;
    }
    setError(null);
    setPhase("requesting_permission");
    const engine = createSpeechRecognition({
      onInterim: (text) => {
        setInterim(text);
        setPhase("listening");
      },
      onFinal: (text) => {
        setTranscript((prev) => (prev ? `${prev} ${text}` : text));
        setInterim("");
        setPhase("processing");
        options?.onFinalTranscript?.(text);
      },
      onError: (message) => {
        setError(message);
        setPhase("error");
      },
      onEnd: () => {
        setPhase((p) => (p === "listening" || p === "requesting_permission" ? "idle" : p));
        engineRef.current = null;
      },
    });
    if (!engine) {
      setError("Speech recognition is not available.");
      setPhase("error");
      return;
    }
    engineRef.current = engine;
    try {
      engine.start();
      setPhase("listening");
    } catch {
      setError("Could not start microphone.");
      setPhase("error");
    }
  }, [available, options]);

  const stopListening = useCallback(() => {
    engineRef.current?.stop();
    setPhase("idle");
    setInterim("");
  }, []);

  useEffect(() => () => engineRef.current?.cancel(), []);

  return {
    available,
    phase,
    setPhase,
    transcript,
    setTranscript,
    interim,
    error,
    startListening,
    stopListening,
    cancel,
    resetTranscript,
    displayText: interim || transcript,
  };
}
