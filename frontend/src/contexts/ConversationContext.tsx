"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ChatMessage, Conversation } from "@/lib/domain/types";

const STORAGE_CONVERSATIONS_KEY = "hey_canvas_conversations_v1.2";
const STORAGE_ACTIVE_ID_KEY = "hey_canvas_active_conversation_id_v1.2";
const MAX_CONVERSATIONS = 50;
const MAX_MESSAGES_PER_CONVERSATION = 100;

export interface ConversationContextValue {
  conversation: Conversation;
  conversationEpoch: number;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  startNewConversation: (courseId?: string) => void;
  conversations: Conversation[];
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  clearAllConversations: () => void;
}

const ConversationContext = createContext<ConversationContextValue | null>(null);

export function newConversation(courseId?: string): Conversation {
  const id = `conv-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  return {
    id,
    title: "New conversation",
    messages: [],
    courseId,
    updatedAt: new Date().toISOString(),
  };
}

function deriveConversationTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user" && m.text?.trim());
  if (!firstUser?.text) return "New conversation";
  const clean = firstUser.text.trim().replace(/[\r\n]+/g, " ");
  return clean.length > 40 ? `${clean.slice(0, 37)}...` : clean;
}

function loadSavedConversations(): { list: Conversation[]; activeId: string | null } {
  if (typeof window === "undefined") {
    return { list: [], activeId: null };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_CONVERSATIONS_KEY);
    const list = raw ? (JSON.parse(raw) as Conversation[]) : [];
    const activeId = window.localStorage.getItem(STORAGE_ACTIVE_ID_KEY);
    return { list: Array.isArray(list) ? list : [], activeId };
  } catch {
    return { list: [], activeId: null };
  }
}

function persistToStorage(list: Conversation[], activeId?: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      STORAGE_CONVERSATIONS_KEY,
      JSON.stringify(list.slice(0, MAX_CONVERSATIONS)),
    );
    if (activeId) {
      window.localStorage.setItem(STORAGE_ACTIVE_ID_KEY, activeId);
    }
  } catch {
    // Graceful handling for quota errors or private browsing
  }
}

export function ConversationProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>(() => [newConversation()]);
  const [activeConversationId, setActiveConversationId] = useState<string>(() => conversations[0].id);
  const [conversationEpoch, setConversationEpoch] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const isHydratedRef = useRef(false);

  // Restore persisted state on client mount
  useEffect(() => {
    const { list, activeId } = loadSavedConversations();
    if (list.length > 0) {
      const active = (activeId && list.find((c) => c.id === activeId)) || list[0];
      queueMicrotask(() => {
        setConversations(list);
        setActiveConversationId(active.id);
        setMessages(active.messages || []);
        setConversationEpoch((e) => e + 1);
      });
    }
    isHydratedRef.current = true;
  }, []);

  const conversation = useMemo(() => {
    return (
      conversations.find((c) => c.id === activeConversationId) ||
      conversations[0] ||
      newConversation()
    );
  }, [conversations, activeConversationId]);

  // Synchronize message changes to conversations array and localStorage
  useEffect(() => {
    if (!isHydratedRef.current) return;

    setConversations((prev) => {
      const index = prev.findIndex((c) => c.id === activeConversationId);
      const boundedMessages = messages.slice(-MAX_MESSAGES_PER_CONVERSATION);
      const current = index >= 0 ? prev[index] : newConversation();
      const updatedTitle =
        current.title === "New conversation"
          ? deriveConversationTitle(boundedMessages)
          : current.title;

      const updated: Conversation = {
        ...current,
        id: activeConversationId,
        messages: boundedMessages,
        title: updatedTitle,
        updatedAt: new Date().toISOString(),
      };

      const nextList =
        index >= 0
          ? [updated, ...prev.filter((c) => c.id !== activeConversationId)]
          : [updated, ...prev];

      persistToStorage(nextList, activeConversationId);
      return nextList;
    });
  }, [messages, activeConversationId]);

  const startNewConversation = useCallback((courseId?: string) => {
    const created = newConversation(courseId);
    setConversations((prev) => {
      const next = [created, ...prev.filter((c) => c.messages.length > 0)];
      persistToStorage(next, created.id);
      return next;
    });
    setActiveConversationId(created.id);
    setMessages([]);
    setConversationEpoch((e) => e + 1);
  }, []);

  const selectConversation = useCallback(
    (id: string) => {
      if (id === activeConversationId) return;
      const target = conversations.find((c) => c.id === id);
      if (!target) return;

      setActiveConversationId(target.id);
      setMessages(target.messages || []);
      setConversationEpoch((e) => e + 1);
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(STORAGE_ACTIVE_ID_KEY, target.id);
        } catch {}
      }
    },
    [activeConversationId, conversations],
  );

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (next.length === 0) {
          const fresh = newConversation();
          setActiveConversationId(fresh.id);
          setMessages([]);
          setConversationEpoch((e) => e + 1);
          persistToStorage([fresh], fresh.id);
          return [fresh];
        }

        if (id === activeConversationId) {
          const nextActive = next[0];
          setActiveConversationId(nextActive.id);
          setMessages(nextActive.messages || []);
          setConversationEpoch((e) => e + 1);
          persistToStorage(next, nextActive.id);
        } else {
          persistToStorage(next, activeConversationId);
        }
        return next;
      });
    },
    [activeConversationId],
  );

  const clearAllConversations = useCallback(() => {
    const fresh = newConversation();
    setConversations([fresh]);
    setActiveConversationId(fresh.id);
    setMessages([]);
    setConversationEpoch((e) => e + 1);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(STORAGE_CONVERSATIONS_KEY);
        window.localStorage.setItem(STORAGE_ACTIVE_ID_KEY, fresh.id);
      } catch {}
    }
  }, []);

  const value = useMemo(
    () => ({
      conversation,
      conversationEpoch,
      messages,
      setMessages,
      startNewConversation,
      conversations,
      selectConversation,
      deleteConversation,
      clearAllConversations,
    }),
    [
      conversation,
      conversationEpoch,
      messages,
      startNewConversation,
      conversations,
      selectConversation,
      deleteConversation,
      clearAllConversations,
    ],
  );

  return (
    <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>
  );
}

export function useConversation() {
  const ctx = useContext(ConversationContext);
  if (!ctx) throw new Error("useConversation must be used within ConversationProvider");
  return ctx;
}
