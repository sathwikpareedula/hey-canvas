/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { reduceWakeWordPhase, wakeWordUnsupportedLabel } from "@/lib/voice/wake-word-state";
import { containsWakePhrase, extractCommandAfterWake } from "@/lib/voice/wake-phrase";

describe("wake phrase", () => {
  it("detects hey canvas", () => {
    expect(containsWakePhrase("Hey Canvas what is due")).toBe(true);
    expect(containsWakePhrase("hello there")).toBe(false);
  });

  it("extracts command", () => {
    expect(extractCommandAfterWake("hey canvas what do I have due")).toBe("what do i have due");
  });

  it("ignores wake phrase without trailing command", () => {
    expect(extractCommandAfterWake("hey canvas")).toBe("");
    expect(extractCommandAfterWake("Hey Canvas!")).toBe("");
  });

  it("does not false-positive on similar words", () => {
    expect(containsWakePhrase("canvas hey there")).toBe(false);
  });
});

describe("wakeWordUnsupportedLabel", () => {
  it("explains unsupported browsers", () => {
    expect(wakeWordUnsupportedLabel(false)).toMatch(/push-to-talk/i);
    expect(wakeWordUnsupportedLabel(true)).toBeNull();
  });
});

describe("wake word state machine", () => {
  it("wake to listening to thinking", () => {
    let p = reduceWakeWordPhase("waiting_wake", { type: "wake_detected" });
    expect(p).toBe("listening_command");
    p = reduceWakeWordPhase(p, { type: "command_captured", command: "hi" });
    expect(p).toBe("thinking");
  });

  it("pauses for tts", () => {
    let p = reduceWakeWordPhase("thinking", { type: "tts_started" });
    expect(p).toBe("speaking");
    p = reduceWakeWordPhase(p, { type: "tts_ended" });
    expect(p).toBe("waiting_wake");
  });

  it("disable", () => {
    expect(reduceWakeWordPhase("waiting_wake", { type: "disable" })).toBe("disabled");
  });

  it("ignores duplicate wake while listening", () => {
    expect(reduceWakeWordPhase("listening_command", { type: "wake_detected" })).toBe(
      "listening_command",
    );
  });

  it("ignores wake while speaking", () => {
    expect(reduceWakeWordPhase("speaking", { type: "wake_detected" })).toBe("speaking");
  });
});
