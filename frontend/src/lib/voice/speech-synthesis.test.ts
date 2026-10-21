/**
 * @vitest-environment node
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { isSpeechSynthesisAvailable, speakText, stopSpeaking } from "@/lib/voice/speech-synthesis";

describe("speech-synthesis", () => {
  beforeEach(() => {
    const speak = vi.fn();
    const cancel = vi.fn();
    class MockUtterance {
      text: string;
      rate = 1;
      constructor(text: string) {
        this.text = text;
      }
    }
    const win = {
      speechSynthesis: { speak, cancel, speaking: false },
      SpeechSynthesisUtterance: MockUtterance,
    };
    (globalThis as unknown as { window: typeof win }).window = win;
  });

  it("speaks text", () => {
    expect(isSpeechSynthesisAvailable()).toBe(true);
    speakText("Hi");
    expect(window.speechSynthesis.speak).toHaveBeenCalled();
  });

  it("stops speech", () => {
    stopSpeaking();
    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
  });
});
