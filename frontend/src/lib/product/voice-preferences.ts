const KEY = "hey-canvas-voice-preferences-v1";

export interface VoicePreferences {
  wakeWordEnabled: boolean;
  autoSpeakResponses: boolean;
}

const DEFAULT: VoicePreferences = {
  wakeWordEnabled: false,
  autoSpeakResponses: false,
};

export function readVoicePreferences(): VoicePreferences {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw) as VoicePreferences;
    return {
      wakeWordEnabled: Boolean(parsed.wakeWordEnabled),
      autoSpeakResponses: Boolean(parsed.autoSpeakResponses),
    };
  } catch {
    return DEFAULT;
  }
}

export function saveVoicePreferences(patch: Partial<VoicePreferences>): VoicePreferences {
  const next = { ...readVoicePreferences(), ...patch };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  }
  return next;
}
