import { describe, expect, it } from "vitest";
import {
  applyTransportEvent,
  canSendAssistantMessage,
  initialAssistantSessionState,
} from "@/lib/assistant/session-controller";

describe("assistant session controller", () => {
  it("allows send only from terminal phases", () => {
    expect(canSendAssistantMessage("idle")).toBe(true);
    expect(canSendAssistantMessage("completed")).toBe(true);
    expect(canSendAssistantMessage("failed")).toBe(true);
    expect(canSendAssistantMessage("cancelled")).toBe(true);
    expect(canSendAssistantMessage("sending")).toBe(false);
    expect(canSendAssistantMessage("streaming")).toBe(false);
  });

  it("accumulates text deltas while streaming", () => {
    let state = initialAssistantSessionState();
    state = applyTransportEvent(state, { type: "start" }).state;
    state = applyTransportEvent(state, { type: "text_delta", delta: "Hi " }).state;
    state = applyTransportEvent(state, { type: "text_delta", delta: "there" }).state;
    expect(state.phase).toBe("streaming");
    expect(state.streamingText).toBe("Hi there");
  });

  it("sanitizes unknown blocks", () => {
    let state = initialAssistantSessionState();
    state = applyTransportEvent(state, {
      type: "block",
      block: { type: "future_block" as "text", content: "x" },
    }).state;
    expect(state.pendingBlocks?.[0]?.type).toBe("warning");
  });

  it("marks cancelled generations with incomplete status", () => {
    const result = applyTransportEvent(initialAssistantSessionState(), { type: "cancelled" });
    expect(result.state.phase).toBe("cancelled");
    expect(result.appendMessage?.status).toBe("incomplete_data");
  });

  it("replaces empty complete message with recovery", () => {
    const result = applyTransportEvent(initialAssistantSessionState(), {
      type: "complete",
      message: {
        id: "empty",
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: [],
      },
    });
    expect(result.appendMessage?.blocks?.[0]?.type).toBe("error");
    expect(result.appendMessage?.blocks?.[0]?.content).toMatch(/did not return/i);
  });

  it("merges trailing stream text into empty complete blocks", () => {
    let state = initialAssistantSessionState();
    state = applyTransportEvent(state, { type: "start" }).state;
    state = applyTransportEvent(state, { type: "text_delta", delta: "Partial" }).state;
    const result = applyTransportEvent(state, {
      type: "complete",
      message: {
        id: "c1",
        role: "assistant",
        createdAt: new Date().toISOString(),
        status: "complete",
        blocks: [],
      },
    });
    expect(result.appendMessage?.blocks?.some((b) => b.type === "text" && b.content === "Partial")).toBe(
      true,
    );
  });

  it("completes with assistant message", () => {
    const message = {
      id: "m1",
      role: "assistant" as const,
      createdAt: new Date().toISOString(),
      status: "complete" as const,
      blocks: [{ type: "text" as const, content: "Done" }],
    };
    const result = applyTransportEvent(initialAssistantSessionState(), {
      type: "complete",
      message,
    });
    expect(result.state.phase).toBe("completed");
    expect(result.appendMessage).toEqual(message);
  });

  it.each(["error", "transport_error", "cancelled"] as const)(
    "drops all provisional sources and text after %s",
    (type) => {
      let state = initialAssistantSessionState();
      state = applyTransportEvent(state, { type: "start" }).state;
      state = applyTransportEvent(state, { type: "text_delta", delta: "Unverified" }).state;
      state = applyTransportEvent(state, {
        type: "block",
        block: { type: "text", content: "Unverified citation claim" },
      }).state;
      expect(state.pendingBlocks?.length).toBe(1);
      const event = type === "error"
        ? { type: "error" as const, message: "Invalid result" }
        : type === "transport_error"
          ? { type: "transport_error" as const, error: new Error("network") }
          : { type: "cancelled" as const };
      const result = applyTransportEvent(state, event);
      expect(result.state.streamingText).toBe("");
      expect(result.state.pendingBlocks).toEqual([]);
      expect(result.state.pendingSources).toBe(0);
      expect(result.appendMessage?.status).not.toBe("complete");
    },
  );

});
