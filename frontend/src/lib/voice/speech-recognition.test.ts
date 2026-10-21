/**
 * @vitest-environment node
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  createSpeechRecognition,
  isSpeechRecognitionAvailable,
} from "@/lib/voice/speech-recognition";

class MockRecognition {
  lang = "en-US";
  continuous = false;
  interimResults = true;
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: { error?: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn(() => {
    this.onresult?.({
      results: [{ isFinal: true, 0: { transcript: "hello world" } }],
    });
    this.onend?.();
  });
  stop = vi.fn(() => this.onend?.());
  abort = vi.fn(() => this.onend?.());
}

describe("speech-recognition", () => {
  beforeEach(() => {
    (globalThis as unknown as { window: { webkitSpeechRecognition: typeof MockRecognition } }).window =
      {
        webkitSpeechRecognition: MockRecognition,
      };
  });

  it("detects availability", () => {
    expect(isSpeechRecognitionAvailable()).toBe(true);
  });

  it("returns final transcript", () => {
    const finals: string[] = [];
    const engine = createSpeechRecognition({ onFinal: (t) => finals.push(t) });
    engine?.start();
    expect(finals).toEqual(["hello world"]);
  });

  it("maps no-speech errors", () => {
    class NoSpeechRecognition extends MockRecognition {
      start = vi.fn(() => {
        this.onerror?.({ error: "no-speech" });
      });
    }
    (globalThis as unknown as { window: { webkitSpeechRecognition: typeof NoSpeechRecognition } }).window =
      {
        webkitSpeechRecognition: NoSpeechRecognition,
      };
    const errors: string[] = [];
    const engine = createSpeechRecognition({ onError: (m) => errors.push(m) });
    engine?.start();
    expect(errors[0]?.toLowerCase()).toMatch(/speech|heard|microphone/i);
  });

  it("maps permission errors", () => {
    class DenyRecognition extends MockRecognition {
      start = vi.fn(() => {
        this.onerror?.({ error: "not-allowed" });
      });
    }
    (globalThis as unknown as { window: { webkitSpeechRecognition: typeof DenyRecognition } }).window =
      {
        webkitSpeechRecognition: DenyRecognition,
      };
    const errors: string[] = [];
    const engine = createSpeechRecognition({ onError: (m) => errors.push(m) });
    engine?.start();
    expect(errors[0]?.toLowerCase()).toContain("permission");
  });
});
