"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { presentAcademicError } from "@/lib/api/error-presentation";
import { createAssistantTransport } from "@/lib/assistant/create-assistant-transport";
import { mapUiRequestToTransport } from "@/lib/assistant/request-mapper";
import {
  applyTransportEvent,
  beginSending,
  canSendAssistantMessage,
  initialAssistantSessionState,
} from "@/lib/assistant/session-controller";
import type { AssistantConversationPhase } from "@/lib/assistant/stream-events";
import { extractPracticeSessionIdFromBlocks } from "@/lib/api/http/assistant-structured-blocks";
import { shouldClearActivePracticeSession } from "@/lib/assistant/practice-session-state";
import type { AssistantRequest } from "@/lib/domain/assistant";
import {
  ASSISTANT_EMPTY_RECOVERY_MESSAGE,
  messageHasVisibleAssistantContent,
} from "@/lib/assistant/empty-response";
import type { ChatMessage } from "@/lib/domain/types";

export function useAssistantSession(options: {
  conversationId: string;
  conversationEpoch: number;
  onMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  onTransportError?: (error: unknown) => void;
  onAssistantMessage?: (message: ChatMessage) => void;
}) {
  const api = useAcademicApi();
  const transportRef = useRef(createAssistantTransport(api));
  const [session, setSession] = useState(initialAssistantSessionState);
  const runIdRef = useRef(0);
  const conversationEpochRef = useRef(options.conversationEpoch);
  const phaseRef = useRef<AssistantConversationPhase>("idle");
  const abortRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<AssistantRequest | null>(null);
  const practiceSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    conversationEpochRef.current = options.conversationEpoch;
  }, [options.conversationEpoch]);

  useEffect(() => {
    phaseRef.current = session.phase;
  }, [session.phase]);

  const isActive = session.phase === "sending" || session.phase === "streaming";

  const cancel = useCallback(() => {
    runIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    const result = applyTransportEvent(initialAssistantSessionState(), { type: "cancelled" });
    phaseRef.current = result.state.phase;
    setSession(result.state);
    if (result.appendMessage) {
      options.onMessages((m) => [...m, result.appendMessage!]);
    }
  }, [options]);

  const send = useCallback(
    async (request: AssistantRequest, sendOptions?: { retry?: boolean }) => {
      const trimmed = request.prompt.trim();
      if (!trimmed || !canSendAssistantMessage(phaseRef.current)) return;

      const runId = ++runIdRef.current;
      const epochAtStart = conversationEpochRef.current;
      lastRequestRef.current = request;

      abortRef.current?.abort();
      const abort = new AbortController();
      abortRef.current = abort;

      if (sendOptions?.retry) {
        options.onMessages((m) => {
          const next = [...m];
          while (next.length && next[next.length - 1]?.role === "assistant") {
            const last = next[next.length - 1];
            if (last?.status === "error" || last?.status === "incomplete_data") {
              next.pop();
              continue;
            }
            break;
          }
          return next;
        });
      } else {
        const userMsg: ChatMessage = {
          id: `u-${Date.now()}`,
          role: "user",
          createdAt: new Date().toISOString(),
          text: trimmed,
        };
        options.onMessages((m) => [...m, userMsg]);
      }

      let localState = beginSending(initialAssistantSessionState());
      phaseRef.current = localState.phase;
      setSession(localState);

      const mergedRequest: AssistantRequest = {
        ...request,
        practiceSessionId:
          request.practiceSessionId ?? practiceSessionIdRef.current ?? undefined,
      };
      const transportRequest = mapUiRequestToTransport({
        ...mergedRequest,
        conversationId: options.conversationId,
      });

      let sawAssistantMessage = false;

      try {
        for await (const event of transportRef.current.send(transportRequest, {
          signal: abort.signal,
        })) {
          if (runId !== runIdRef.current) return;
          if (epochAtStart !== conversationEpochRef.current) return;

          const result = applyTransportEvent(localState, event);
          localState = result.state;
          phaseRef.current = localState.phase;
          setSession(localState);

          if (result.appendMessage) {
            let message = result.appendMessage;
            if (result.transportError) {
              const presented = presentAcademicError(result.transportError);
              message = {
                ...message,
                blocks: [{ type: "error", content: presented.message }],
              };
            }
            if (message.role === "assistant" && messageHasVisibleAssistantContent(message)) {
              sawAssistantMessage = true;
            }
            options.onMessages((m) => [...m, message]);
            if (message.role === "assistant") {
              if (shouldClearActivePracticeSession(message.blocks)) {
                practiceSessionIdRef.current = null;
              } else {
                const practiceId = extractPracticeSessionIdFromBlocks(message.blocks);
                if (practiceId) practiceSessionIdRef.current = practiceId;
              }
              options.onAssistantMessage?.(message);
            }
          }
          if (result.transportError) {
            options.onTransportError?.(result.transportError);
          }
        }
      } catch (err) {
        if (runId !== runIdRef.current) return;
        if (epochAtStart !== conversationEpochRef.current) return;
        const result = applyTransportEvent(localState, {
          type: "transport_error",
          error: err,
        });
        phaseRef.current = result.state.phase;
        setSession(result.state);
        if (result.appendMessage) {
          const presented = presentAcademicError(err);
          options.onMessages((m) => [
            ...m,
            {
              ...result.appendMessage!,
              blocks: [{ type: "error", content: presented.message }],
            },
          ]);
        }
        options.onTransportError?.(err);
      } finally {
        if (runId === runIdRef.current) {
          abortRef.current = null;
          const trailingText = localState.streamingText.trim();
          if (
            !sawAssistantMessage &&
            (trailingText || phaseRef.current === "sending" || phaseRef.current === "streaming")
          ) {
            const recovery: ChatMessage = trailingText
              ? {
                  id: `asst-stream-${Date.now()}`,
                  role: "assistant",
                  createdAt: new Date().toISOString(),
                  status: "complete",
                  blocks: [{ type: "text", content: trailingText }],
                }
              : {
                  id: `asst-empty-${Date.now()}`,
                  role: "assistant",
                  createdAt: new Date().toISOString(),
                  status: "error",
                  blocks: [{ type: "error", content: ASSISTANT_EMPTY_RECOVERY_MESSAGE }],
                };
            options.onMessages((m) => [...m, recovery]);
            sawAssistantMessage = true;
          }
          if (phaseRef.current === "sending" || phaseRef.current === "streaming") {
            phaseRef.current = "completed";
            setSession({ ...initialAssistantSessionState(), phase: "completed" });
          }
        }
      }
    },
    [options],
  );

  const retryLast = useCallback(() => {
    const last = lastRequestRef.current;
    if (last) void send(last, { retry: true });
  }, [send]);

  const resetSession = useCallback(() => {
    runIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    phaseRef.current = "idle";
    practiceSessionIdRef.current = null;
    // A new conversation must not retry a prompt from the prior conversation.
    lastRequestRef.current = null;
    setSession(initialAssistantSessionState());
  }, []);

  const clearPracticeSession = useCallback(() => {
    practiceSessionIdRef.current = null;
  }, []);

  return {
    phase: session.phase,
    streamingText: session.streamingText,
    isActive,
    send,
    cancel,
    retryLast,
    resetSession,
    pendingSources: session.pendingSources,
    activityMessage: session.activityMessage,
    clearPracticeSession,
    getPracticeSessionId: () => practiceSessionIdRef.current,
  };
}
