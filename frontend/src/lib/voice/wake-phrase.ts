export const WAKE_PHRASE = "hey canvas";

export function normalizeSpeechText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function containsWakePhrase(text: string): boolean {
  return normalizeSpeechText(text).includes(WAKE_PHRASE);
}

/** Text after the first wake phrase occurrence. */
export function extractCommandAfterWake(text: string): string {
  const norm = normalizeSpeechText(text);
  const idx = norm.indexOf(WAKE_PHRASE);
  if (idx < 0) return "";
  return norm.slice(idx + WAKE_PHRASE.length).trim();
}
