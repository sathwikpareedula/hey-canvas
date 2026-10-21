export function isSpeechSynthesisAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speakText(
  text: string,
  options?: { rate?: number; onEnd?: () => void },
): void {
  if (!isSpeechSynthesisAvailable() || !text.trim()) return;
  window.speechSynthesis.cancel();
  const UtteranceCtor = window.SpeechSynthesisUtterance;
  if (!UtteranceCtor) return;
  const utterance = new UtteranceCtor(text);
  utterance.rate = options?.rate ?? 1;
  utterance.onend = () => options?.onEnd?.();
  utterance.onerror = () => options?.onEnd?.();
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if (!isSpeechSynthesisAvailable()) return;
  window.speechSynthesis.cancel();
}

export function isSpeaking(): boolean {
  if (!isSpeechSynthesisAvailable()) return false;
  return window.speechSynthesis.speaking;
}
