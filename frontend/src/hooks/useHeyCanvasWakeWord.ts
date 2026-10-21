"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSpeechRecognition,
  isSpeechRecognitionAvailable,
} from "@/lib/voice/speech-recognition";
import {
  containsWakePhrase,
  extractCommandAfterWake,
} from "@/lib/voice/wake-phrase";
import {
  reduceWakeWordPhase,
  wakePhaseStudentLabel,
  type WakeWordPhase,
} from "@/lib/voice/wake-word-state";

export function useHeyCanvasWakeWord(options: {
  enabled: boolean;
  paused: boolean;
  onCommand: (command: string) => void;
}) {
  const [phase, setPhase] = useState<WakeWordPhase>("disabled");
  const phaseRef = useRef<WakeWordPhase>("disabled");
  const engineRef = useRef<ReturnType<typeof createSpeechRecognition>>(null);
  const commandBufferRef = useRef("");
  const wakeHandledRef = useRef(false);
  const commandSubmittedRef = useRef(false);
  const onCommandRef = useRef(options.onCommand);
  const pausedRef = useRef(options.paused);
  const enabledRef = useRef(options.enabled);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const available = isSpeechRecognitionAvailable();

  const clearRestartTimer = useCallback(() => {
    if (restartTimerRef.current !== null) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  }, []);

  const stopEngine = useCallback(() => {
    clearRestartTimer();
    engineRef.current?.cancel();
    engineRef.current = null;
  }, [clearRestartTimer]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      clearRestartTimer();
      stopEngine();
    };
  }, [clearRestartTimer, stopEngine]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    onCommandRef.current = options.onCommand;
    pausedRef.current = options.paused;
    enabledRef.current = options.enabled;
  }, [options.onCommand, options.paused, options.enabled]);

  const dispatch = useCallback((event: Parameters<typeof reduceWakeWordPhase>[1]) => {
    if (!isMountedRef.current) return;
    setPhase((p) => {
      const next = reduceWakeWordPhase(p, event);
      phaseRef.current = next;
      return next;
    });
  }, []);

  const startEngineRef = useRef<(continuous: boolean) => void>(() => {});

  const scheduleRestart = useCallback(
    (delayMs: number, continuous: boolean) => {
      clearRestartTimer();
      restartTimerRef.current = setTimeout(() => {
        restartTimerRef.current = null;
        if (isMountedRef.current && !pausedRef.current && enabledRef.current) {
          startEngineRef.current(continuous);
        }
      }, delayMs);
    },
    [clearRestartTimer],
  );

  useEffect(() => {
    startEngineRef.current = (continuous: boolean) => {
    if (!available || pausedRef.current) return;
    stopEngine();
    wakeHandledRef.current = false;
    commandSubmittedRef.current = false;
    commandBufferRef.current = "";
    const engine = createSpeechRecognition({
      continuous,
      onInterim: (text) => {
        if (pausedRef.current) return;
        const p = phaseRef.current;
        if (p === "waiting_wake" && containsWakePhrase(text)) {
          dispatch({ type: "wake_detected" });
          const cmd = extractCommandAfterWake(text);
          if (cmd.length > 2) commandBufferRef.current = cmd;
          wakeHandledRef.current = true;
        } else if (p === "listening_command") {
          commandBufferRef.current = text.trim();
        }
      },
      onFinal: (text) => {
        if (pausedRef.current) return;
        const p = phaseRef.current;
        if (p === "waiting_wake" && containsWakePhrase(text)) {
          dispatch({ type: "wake_detected" });
          const cmd = extractCommandAfterWake(text);
          if (cmd.length > 2) commandBufferRef.current = cmd;
          else wakeHandledRef.current = true;
          return;
        }
        if (p === "listening_command") {
          commandBufferRef.current = (commandBufferRef.current
            ? `${commandBufferRef.current} ${text}`
            : text
          ).trim();
        }
      },
      onError: (message) => {
        if (message.toLowerCase().includes("permission")) {
          dispatch({ type: "permission_denied" });
        } else {
          dispatch({ type: "recognition_error" });
        }
        stopEngine();
      },
      onEnd: () => {
        if (pausedRef.current) {
          engineRef.current = null;
          return;
        }
        const p = phaseRef.current;
        if (p === "listening_command") {
          const cmd = commandBufferRef.current.trim();
          if (cmd.length > 0 && !commandSubmittedRef.current) {
            commandSubmittedRef.current = true;
            dispatch({ type: "command_captured", command: cmd });
            onCommandRef.current(cmd);
            commandBufferRef.current = "";
          } else if (wakeHandledRef.current) {
            dispatch({ type: "reset" });
          }
        }
        engineRef.current = null;
        if (!pausedRef.current && enabledRef.current && (p === "waiting_wake" || p === "listening_command")) {
          scheduleRestart(300, phaseRef.current === "waiting_wake");
        }
      },
    });
    if (!engine) return;
    engineRef.current = engine;
    try {
      engine.start();
    } catch {
      dispatch({ type: "recognition_error" });
    }
    };
  }, [available, dispatch, stopEngine, scheduleRestart]);

  useEffect(() => {
    if (!options.enabled || !available) {
      stopEngine();
      const id = window.setTimeout(() => setPhase("disabled"), 0);
      return () => {
        window.clearTimeout(id);
        stopEngine();
      };
    }
    if (options.paused) {
      stopEngine();
      commandBufferRef.current = "";
      commandSubmittedRef.current = false;
      return () => stopEngine();
    }
    const id = window.setTimeout(() => {
      setPhase("waiting_wake");
      startEngineRef.current(true);
    }, 0);
    return () => {
      window.clearTimeout(id);
      stopEngine();
    };
  }, [options.enabled, options.paused, available, stopEngine]);

  const notifySpeaking = useCallback(
    (speaking: boolean) => {
      if (speaking) {
        stopEngine();
        dispatch({ type: "tts_started" });
      } else {
        dispatch({ type: "tts_ended" });
        if (isMountedRef.current && enabledRef.current && !pausedRef.current) {
          scheduleRestart(400, true);
        }
      }
    },
    [dispatch, stopEngine, scheduleRestart],
  );

  const cancel = useCallback(() => {
    stopEngine();
    dispatch({ type: "cancel" });
    if (isMountedRef.current && enabledRef.current && !pausedRef.current) {
      scheduleRestart(300, true);
    }
  }, [dispatch, stopEngine, scheduleRestart]);

  return {
    available,
    phase,
    label: wakePhaseStudentLabel(phase),
    notifySpeaking,
    cancel,
    setThinking: () => dispatch({ type: "assistant_started" }),
  };
}
