export type WakeWordPhase =
  | "disabled"
  | "waiting_wake"
  | "listening_command"
  | "thinking"
  | "speaking"
  | "error";

export type WakeWordEvent =
  | { type: "enable" }
  | { type: "disable" }
  | { type: "wake_detected" }
  | { type: "command_captured"; command: string }
  | { type: "assistant_started" }
  | { type: "tts_started" }
  | { type: "tts_ended" }
  | { type: "permission_denied" }
  | { type: "recognition_error" }
  | { type: "cancel" }
  | { type: "reset" };

export function reduceWakeWordPhase(
  phase: WakeWordPhase,
  event: WakeWordEvent,
): WakeWordPhase {
  switch (event.type) {
    case "disable":
      return "disabled";
    case "enable":
      return phase === "disabled" ? "waiting_wake" : phase;
    case "wake_detected":
      if (phase === "waiting_wake") return "listening_command";
      return phase;
    case "command_captured":
      return "thinking";
    case "assistant_started":
      return "thinking";
    case "tts_started":
      return "speaking";
    case "tts_ended":
      return "waiting_wake";
    case "permission_denied":
    case "recognition_error":
      return "error";
    case "cancel":
      return phase === "disabled" ? "disabled" : "waiting_wake";
    case "reset":
      return "waiting_wake";
    default:
      return phase;
  }
}

export function wakePhaseStudentLabel(phase: WakeWordPhase): string | null {
  switch (phase) {
    case "waiting_wake":
      return 'Waiting for "Hey Canvas"…';
    case "listening_command":
      return "Listening…";
    case "thinking":
      return "Thinking…";
    case "speaking":
      return "Speaking…";
    case "error":
      return "Voice needs attention — check microphone permission.";
    case "disabled":
      return null;
    default:
      return null;
  }
}

export function wakeWordUnsupportedLabel(speechRecognitionAvailable: boolean): string | null {
  if (speechRecognitionAvailable) return null;
  return "Hands-free voice is not supported in this browser. Use push-to-talk on the mic button.";
}
