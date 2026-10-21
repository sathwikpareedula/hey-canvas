import { act, renderHook } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it } from "vitest";
import {
  ConversationProvider,
  useConversation,
} from "./ConversationContext";
import type { ChatMessage } from "@/lib/domain/types";

describe("ConversationContext", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <ConversationProvider>{children}</ConversationProvider>
  );

  it("initializes with a default conversation and empty messages", () => {
    const { result } = renderHook(() => useConversation(), { wrapper });
    expect(result.current.conversation).toBeDefined();
    expect(result.current.conversation.title).toBe("New conversation");
    expect(result.current.messages).toEqual([]);
    expect(result.current.conversations.length).toBeGreaterThanOrEqual(1);
  });

  it("saves messages and derives conversation title from first user query", async () => {
    const { result } = renderHook(() => useConversation(), { wrapper });

    const userMsg: ChatMessage = {
      id: "u1",
      role: "user",
      createdAt: new Date().toISOString(),
      text: "What assignments are due this month?",
    };

    act(() => {
      result.current.setMessages([userMsg]);
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.conversation.title).toBe("What assignments are due this month?");

    // Check localStorage
    const savedRaw = window.localStorage.getItem("hey_canvas_conversations_v1.2");
    expect(savedRaw).toBeTruthy();
    const parsed = JSON.parse(savedRaw!);
    expect(parsed[0].title).toBe("What assignments are due this month?");
    expect(parsed[0].messages).toHaveLength(1);
  });

  it("supports starting a new conversation and switching back", () => {
    const { result } = renderHook(() => useConversation(), { wrapper });

    // Send message in first conversation
    act(() => {
      result.current.setMessages([
        {
          id: "u1",
          role: "user",
          createdAt: new Date().toISOString(),
          text: "First conversation query",
        },
      ]);
    });

    const firstConvId = result.current.conversation.id;

    // Start new conversation
    act(() => {
      result.current.startNewConversation();
    });

    const secondConvId = result.current.conversation.id;
    expect(secondConvId).not.toBe(firstConvId);
    expect(result.current.messages).toEqual([]);

    // Send message in second conversation
    act(() => {
      result.current.setMessages([
        {
          id: "u2",
          role: "user",
          createdAt: new Date().toISOString(),
          text: "Second conversation query",
        },
      ]);
    });

    expect(result.current.conversation.title).toBe("Second conversation query");
    expect(result.current.conversations).toHaveLength(2);

    // Switch back to first conversation
    act(() => {
      result.current.selectConversation(firstConvId);
    });

    expect(result.current.conversation.id).toBe(firstConvId);
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].text).toBe("First conversation query");
  });

  it("deletes a conversation safely", () => {
    const { result } = renderHook(() => useConversation(), { wrapper });

    act(() => {
      result.current.setMessages([
        {
          id: "u1",
          role: "user",
          createdAt: new Date().toISOString(),
          text: "Delete me query",
        },
      ]);
    });

    const convId = result.current.conversation.id;

    act(() => {
      result.current.deleteConversation(convId);
    });

    // Should create a fresh conversation when the last one is deleted
    expect(result.current.conversation.id).not.toBe(convId);
    expect(result.current.messages).toEqual([]);
  });
});
