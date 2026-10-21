"use client";

import { useSyncExternalStore, useState } from "react";
import { VoiceHandsFreeBar } from "@/components/voice/VoiceHandsFreeBar";
import {
  readVoicePreferences,
  saveVoicePreferences,
} from "@/lib/product/voice-preferences";
import { isSpeechRecognitionAvailable } from "@/lib/voice/speech-recognition";
import { isSpeechSynthesisAvailable } from "@/lib/voice/speech-synthesis";

const emptySubscribe = () => () => {};

export function VoiceSettingsPanel() {
  const [prefs, setPrefs] = useState(() => readVoicePreferences());
  const isClient = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const rec = isClient ? isSpeechRecognitionAvailable() : false;
  const tts = isClient ? isSpeechSynthesisAvailable() : false;

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold">Voice</h2>
      <p className="text-xs text-[var(--muted)]">
        Hands-free mode listens for &quot;Hey Canvas&quot; while this app is open. Audio is processed
        by your browser; Hey Canvas does not store recordings.
      </p>
      <VoiceHandsFreeBar
        wakeEnabled={prefs.wakeWordEnabled}
        wakeAvailable={rec}
        wakePhase={prefs.wakeWordEnabled ? "waiting_wake" : "disabled"}
        wakeLabel={prefs.wakeWordEnabled ? 'Enable on Hey Canvas chat, then say "Hey Canvas"' : null}
        autoSpeak={prefs.autoSpeakResponses}
        autoSpeakAvailable={tts}
        onToggleWake={() => {
          const next = saveVoicePreferences({ wakeWordEnabled: !prefs.wakeWordEnabled });
          setPrefs(next);
        }}
        onToggleAutoSpeak={() => {
          const next = saveVoicePreferences({ autoSpeakResponses: !prefs.autoSpeakResponses });
          setPrefs(next);
        }}
      />
      <ul className="list-disc space-y-1 pl-5 text-xs text-[var(--muted)]">
        <li>Microphone: {rec ? "Supported in this browser" : "Not available — use Chrome/Edge desktop"}</li>
        <li>Spoken responses: {tts ? "Available" : "Not available"}</li>
        <li>Wake phrase works best in a quiet room with permission granted.</li>
      </ul>
    </div>
  );
}
