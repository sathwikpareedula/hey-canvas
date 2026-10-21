export type SpeechRecognitionStatus =
  | "unavailable"
  | "idle"
  | "requesting_permission"
  | "listening"
  | "processing"
  | "error";

export interface SpeechRecognitionCallbacks {
  onInterim?: (text: string) => void;
  onFinal?: (text: string) => void;
  onError?: (message: string) => void;
  onEnd?: () => void;
}

type RecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: { results: { length: number; [index: number]: { isFinal: boolean; 0: { transcript: string } } } }) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

export function isSpeechRecognitionAvailable(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(getRecognitionCtor());
}

function getRecognitionCtor(): (new () => RecognitionInstance) | undefined {
  const w = window as Window & {
    SpeechRecognition?: new () => RecognitionInstance;
    webkitSpeechRecognition?: new () => RecognitionInstance;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export interface ContinuousSpeechOptions extends SpeechRecognitionCallbacks {
  continuous?: boolean;
}

export function createSpeechRecognition(
  callbacks: ContinuousSpeechOptions,
): { start: () => void; stop: () => void; cancel: () => void } | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;

  const recognition = new Ctor();
  recognition.lang = "en-US";
  recognition.continuous = Boolean(callbacks.continuous);
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    let interim = "";
    let final = "";
    for (let i = 0; i < event.results.length; i += 1) {
      const result = event.results[i];
      const transcript = result[0]?.transcript ?? "";
      if (result.isFinal) final += transcript;
      else interim += transcript;
    }
    if (interim.trim()) callbacks.onInterim?.(interim.trim());
    if (final.trim()) callbacks.onFinal?.(final.trim());
  };

  recognition.onerror = (event) => {
    const code = event.error ?? "unknown";
    if (code === "aborted") return;
    callbacks.onError?.(userMessageForRecognitionError(code));
  };

  recognition.onend = () => {
    callbacks.onEnd?.();
  };

  return {
    start: () => recognition.start(),
    stop: () => recognition.stop(),
    cancel: () => recognition.abort(),
  };
}

function userMessageForRecognitionError(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone permission was denied.";
    case "no-speech":
      return "No speech was detected. Try again.";
    case "network":
      return "Speech recognition needs a network connection.";
    default:
      return "Speech recognition failed. Try typing instead.";
  }
}
