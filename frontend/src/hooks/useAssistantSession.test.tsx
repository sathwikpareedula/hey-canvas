import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useAssistantSession } from "@/hooks/useAssistantSession";
import type { ChatMessage } from "@/lib/domain/types";

const mocks = vi.hoisted(() => ({
  send: vi.fn(async function* () {
    // Empty synthetic response exercises the recovery path without a backend.
  }),
}));

vi.mock("@/contexts/AcademicApiContext", () => ({
  useAcademicApi: () => ({}),
}));

vi.mock("@/lib/assistant/create-assistant-transport", () => ({
  createAssistantTransport: () => ({ send: mocks.send }),
}));

describe("useAssistantSession new conversation isolation", () => {
  it("clears the previous request so Retry cannot reopen an old conversation", async () => {
    mocks.send.mockClear();
    let messages: ChatMessage[] = [];
    const updateMessages = (
      next: React.SetStateAction<ChatMessage[]>,
    ) => {
      messages = typeof next === "function" ? next(messages) : next;
    };
    const { result } = renderHook(() =>
      useAssistantSession({
        conversationId: "conversation-1",
        conversationEpoch: 1,
        onMessages: updateMessages,
      }),
    );

    await act(async () => {
      await result.current.send({ prompt: "Explain A* search" });
    });
    expect(mocks.send).toHaveBeenCalledTimes(1);
    expect(messages.some((item) => item.role === "user")).toBe(true);

    act(() => {
      result.current.resetSession();
    });
    act(() => {
      result.current.retryLast();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(mocks.send).toHaveBeenCalledTimes(1);
  });
});
