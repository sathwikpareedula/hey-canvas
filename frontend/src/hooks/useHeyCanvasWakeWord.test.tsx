import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ContinuousSpeechOptions } from "@/lib/voice/speech-recognition";
import { useHeyCanvasWakeWord } from "@/hooks/useHeyCanvasWakeWord";

const engines: Array<{
  callbacks: ContinuousSpeechOptions;
  start: ReturnType<typeof vi.fn>;
  cancel: ReturnType<typeof vi.fn>;
}> = [];

vi.mock("@/lib/voice/speech-recognition", () => ({
  isSpeechRecognitionAvailable: () => true,
  createSpeechRecognition: (callbacks: ContinuousSpeechOptions) => {
    const engine = {
      callbacks,
      start: vi.fn(),
      cancel: vi.fn(),
    };
    engines.push(engine);
    return {
      start: engine.start,
      stop: vi.fn(),
      cancel: engine.cancel,
    };
  },
}));

function activeEngine() {
  const engine = engines.at(-1);
  if (!engine) throw new Error("no mock speech engine");
  return engine;
}

describe("useHeyCanvasWakeWord", () => {
  afterEach(() => {
    cleanup();
    engines.length = 0;
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("starts in waiting_wake when enabled", async () => {
    const onCommand = vi.fn();
    const { result } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await waitFor(() => expect(result.current.phase).toBe("waiting_wake"));
    expect(activeEngine().start).toHaveBeenCalled();
  });

  it("submits command once after wake phrase and end", async () => {
    const onCommand = vi.fn();
    const { result } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await waitFor(() => expect(result.current.phase).toBe("waiting_wake"));
    const { callbacks } = activeEngine();
    act(() => {
      callbacks.onFinal?.("hey canvas what is due tomorrow");
    });
    expect(result.current.phase).toBe("listening_command");
    act(() => {
      callbacks.onEnd?.();
    });
    expect(onCommand).toHaveBeenCalledTimes(1);
    expect(onCommand.mock.calls[0][0]).toContain("what is due tomorrow");
    expect(result.current.phase).toBe("thinking");
  });

  it("does not double-submit when onEnd fires twice", async () => {
    const onCommand = vi.fn();
    renderHook(() => useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }));
    await waitFor(() => expect(engines.length).toBeGreaterThan(0));
    const { callbacks } = activeEngine();
    act(() => {
      callbacks.onFinal?.("hey canvas summarize lecture six");
    });
    act(() => {
      callbacks.onEnd?.();
      callbacks.onEnd?.();
    });
    expect(onCommand).toHaveBeenCalledTimes(1);
  });

  it("pauses recognition while speaking and resumes after TTS", async () => {
    vi.useFakeTimers();
    const onCommand = vi.fn();
    const { result } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    const enginesBefore = engines.length;
    act(() => {
      result.current.notifySpeaking(true);
    });
    expect(result.current.phase).toBe("speaking");
    expect(activeEngine().cancel).toHaveBeenCalled();
    await act(async () => {
      result.current.notifySpeaking(false);
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(engines.length).toBeGreaterThan(enginesBefore);
    expect(result.current.phase).toBe("waiting_wake");
  });

  it("ignores non-wake speech while waiting", async () => {
    const onCommand = vi.fn();
    renderHook(() => useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }));
    await waitFor(() => expect(engines.length).toBeGreaterThan(0));
    const { callbacks } = activeEngine();
    act(() => {
      callbacks.onFinal?.("what is due tomorrow");
      callbacks.onEnd?.();
    });
    expect(onCommand).not.toHaveBeenCalled();
  });

  it("wake phrase alone enters listening without submit", async () => {
    const onCommand = vi.fn();
    const { result } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await waitFor(() => expect(result.current.phase).toBe("waiting_wake"));
    const { callbacks } = activeEngine();
    act(() => {
      callbacks.onFinal?.("hey canvas");
    });
    expect(result.current.phase).toBe("listening_command");
    act(() => {
      callbacks.onEnd?.();
    });
    expect(onCommand).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("waiting_wake");
  });

  it("does not listen while paused", async () => {
    const onCommand = vi.fn();
    const { rerender } = renderHook(
      ({ paused }) => useHeyCanvasWakeWord({ enabled: true, paused, onCommand }),
      { initialProps: { paused: true } },
    );
    await waitFor(() => expect(engines.length).toBe(0));
    rerender({ paused: false });
    await waitFor(() => expect(engines.length).toBeGreaterThan(0));
    const countAfterEnable = engines.length;
    rerender({ paused: true });
    await waitFor(() => expect(activeEngine().cancel).toHaveBeenCalled());
    const { callbacks } = activeEngine();
    act(() => {
      callbacks.onFinal?.("hey canvas open settings");
      callbacks.onEnd?.();
    });
    expect(onCommand).not.toHaveBeenCalled();
    expect(engines.length).toBeGreaterThanOrEqual(countAfterEnable);
  });

  it("stops when disabled", async () => {
    const onCommand = vi.fn();
    const { result, rerender } = renderHook(
      ({ enabled }) => useHeyCanvasWakeWord({ enabled, paused: false, onCommand }),
      { initialProps: { enabled: true } },
    );
    await waitFor(() => expect(result.current.phase).toBe("waiting_wake"));
    rerender({ enabled: false });
    await waitFor(() => expect(result.current.phase).toBe("disabled"));
  });

  it("cancels pending restart timer on unmount without leaking engines", async () => {
    vi.useFakeTimers();
    const onCommand = vi.fn();
    const { unmount } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    const count = engines.length;
    const { callbacks } = activeEngine();
    act(() => {
      callbacks.onEnd?.();
    });
    // Unmount before 300ms restart timer fires
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    // No new engines should have been instantiated after unmount
    expect(engines.length).toBe(count);
  });

  it("cancels restart timer when unmounted immediately after cancel() without leaking engines", async () => {
    vi.useFakeTimers();
    const onCommand = vi.fn();
    const { result, unmount } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    const count = engines.length;
    act(() => {
      result.current.cancel();
    });
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(engines.length).toBe(count);
  });

  it("cancels restart timer when unmounted immediately after notifySpeaking(false) without leaking engines", async () => {
    vi.useFakeTimers();
    const onCommand = vi.fn();
    const { result, unmount } = renderHook(() =>
      useHeyCanvasWakeWord({ enabled: true, paused: false, onCommand }),
    );
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    act(() => {
      result.current.notifySpeaking(true);
    });
    const count = engines.length;
    act(() => {
      result.current.notifySpeaking(false);
    });
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(engines.length).toBe(count);
  });
});
