"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatMessageView } from "@/components/chat/ChatMessage";
import { ContextModeBadge } from "@/components/product/ContextModeBadge";
import { EntityDisambiguationCard } from "@/components/product/EntityDisambiguationCard";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useAssistantSession } from "@/hooks/useAssistantSession";
import { getProductSettingsApi, resolveEntitiesWithFallback } from "@/lib/api/product-settings-service";
import type { DisambiguationCandidate } from "@/lib/domain/product-settings";
import type { ChatMessage, Course } from "@/lib/domain/types";
import {
  buildDeadlineFastPathMessage,
  matchDeadlineFastPath,
} from "@/lib/product/deadline-fast-path";
import { activeAssignmentIdFromMessages } from "@/lib/product/conversation-entity-context";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";
import { useHeyCanvasWakeWord } from "@/hooks/useHeyCanvasWakeWord";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useVoiceOutput } from "@/hooks/useVoiceOutput";
import { VoiceHandsFreeBar } from "@/components/voice/VoiceHandsFreeBar";
import {
  readVoicePreferences,
  saveVoicePreferences,
} from "@/lib/product/voice-preferences";

export function CourseChatPanel({ course }: { course: Course }) {
  const api = useAcademicApi();
  const productApi = getProductSettingsApi();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [epoch] = useState(0);
  const [composerText, setComposerText] = useState("");
  const [disambiguation, setDisambiguation] = useState<{
    title: string;
    candidates: DisambiguationCandidate[];
    pendingPrompt: string;
  } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const conversationId = `course-${course.id}`;
  const [voicePrefs, setVoicePrefs] = useState(() => readVoicePreferences());
  const voiceInput = useVoiceInput();
  const voiceOutput = useVoiceOutput();
  const wakeNotifyRef = useRef<(speaking: boolean) => void>(() => {});

  const {
    send: sendAssistant,
    isActive,
    streamingText,
    cancel,
    activityMessage,
  } = useAssistantSession({
    conversationId,
    conversationEpoch: epoch,
    onMessages: setMessages,
    onAssistantMessage: (message) => {
      if (!voicePrefs.autoSpeakResponses) return;
      voiceInput.setPhase("speaking");
      wakeNotifyRef.current(true);
      voiceOutput.speakMessage(message, () => {
        wakeNotifyRef.current(false);
        voiceInput.setPhase("idle");
      });
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streamingText]);

  const dispatchPrompt = useCallback(
    (text: string, ctx?: { assignmentId?: string; documentId?: string }) => {
      const fastWindow = matchDeadlineFastPath(text);
      if (fastWindow && !ctx?.assignmentId && !ctx?.documentId) {
        const userMsg: ChatMessage = {
          id: `u-${Date.now()}`,
          role: "user",
          createdAt: new Date().toISOString(),
          text,
        };
        setMessages((m) => [...m, userMsg]);
        void (async () => {
          const deadlines = await api.getDeadlines();
          const overdue = await api.getAssignments({
            window: "past_due_time",
            courseId: course.id,
          });
          const allAssignments =
            fastWindow === "next_week"
              ? await api.getAssignments({ window: "next_week", courseId: course.id })
              : undefined;
          setMessages((m) => [
            ...m,
            buildDeadlineFastPathMessage({
              window: fastWindow,
              deadlines,
              overdue,
              courseId: course.id,
              courses: [course],
              allAssignments,
            }),
          ]);
        })();
        return;
      }
      void sendAssistant({
        prompt: text,
        courseId: course.id,
        assignmentId: ctx?.assignmentId,
        documentId: ctx?.documentId,
      });
    },
    [api, course, sendAssistant],
  );

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isActive) return;
      setComposerText("");
      if (matchDeadlineFastPath(trimmed)) {
        dispatchPrompt(trimmed);
        return;
      }
      void (async () => {
        const conversationalAssignmentId = activeAssignmentIdFromMessages(messages) ?? undefined;
        const result = await resolveEntitiesWithFallback(productApi, api, {
          text: trimmed,
          courseId: course.id,
          assignmentId: conversationalAssignmentId,
        });
        if (result.outcome === "ambiguous" && result.candidates.length) {
          setDisambiguation({
            title: result.kind === "assignment" ? "Which assignment did you mean?" : "Which did you mean?",
            candidates: result.candidates,
            pendingPrompt: trimmed,
          });
          return;
        }
        if (result.outcome === "resolved" && result.kind === "assignment" && result.selectedId) {
          dispatchPrompt(trimmed, { assignmentId: result.selectedId });
          return;
        }
        dispatchPrompt(trimmed);
      })();
    },
    [api, productApi, course.id, isActive, dispatchPrompt, messages],
  );

  const wakeThinkingRef = useRef<() => void>(() => {});
  const wakeWord = useHeyCanvasWakeWord({
    enabled: voicePrefs.wakeWordEnabled,
    paused:
      isActive ||
      voiceInput.phase === "speaking" ||
      voiceInput.phase === "listening" ||
      voiceInput.phase === "processing",
    onCommand: (cmd) => {
      wakeThinkingRef.current();
      send(cmd);
    },
  });
  useEffect(() => {
    wakeNotifyRef.current = wakeWord.notifySpeaking;
    wakeThinkingRef.current = wakeWord.setThinking;
  }, [wakeWord.notifySpeaking, wakeWord.setThinking]);

  const onPickDisambiguation = (candidate: DisambiguationCandidate) => {
    const prompt = disambiguation?.pendingPrompt ?? "";
    setDisambiguation(null);
    if (candidate.kind === "course") {
      dispatchPrompt(prompt, { assignmentId: undefined });
      return;
    }
    if (candidate.kind === "assignment") {
      dispatchPrompt(prompt, { assignmentId: candidate.id });
      return;
    }
    dispatchPrompt(prompt, { documentId: candidate.id });
  };

  return (
    <div className="flex min-h-[24rem] flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <ContextModeBadge course={course} scoped />
        <Link
          href={buildHeyCanvasUrl({ courseId: course.id })}
          className="text-xs text-[var(--accent)] underline"
        >
          Open full Hey Canvas
        </Link>
      </div>
      {disambiguation ? (
        <div className="p-3">
          <EntityDisambiguationCard
            title={disambiguation.title}
            candidates={disambiguation.candidates}
            onPick={onPickDisambiguation}
          />
        </div>
      ) : null}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-3">
        {messages.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">
            Ask about this course — assignments, lectures, and study help stay scoped to{" "}
            <span className="font-medium text-[var(--foreground)]">{course.name}</span>.
          </p>
        ) : (
          messages.map((msg) => (
            <ChatMessageView
              key={msg.id}
              message={msg}
              coursesById={new Map([[course.id, course]])}
              onFollowUp={send}
              practiceBusy={isActive}
            />
          ))
        )}
        {streamingText ? (
          <p className="text-sm text-[var(--muted)] whitespace-pre-wrap">{streamingText}</p>
        ) : null}
        {isActive && !streamingText ? (
          <p className="text-sm text-[var(--muted)]" role="status">{activityMessage ?? "Working…"}</p>
        ) : null}
      </div>
      <div className="border-t border-[var(--border)] p-2">
        <VoiceHandsFreeBar
          wakeEnabled={voicePrefs.wakeWordEnabled}
          wakeAvailable={wakeWord.available}
          wakePhase={wakeWord.phase}
          wakeLabel={wakeWord.label}
          autoSpeak={voicePrefs.autoSpeakResponses}
          autoSpeakAvailable={voiceOutput.available}
          onToggleWake={() =>
            setVoicePrefs(saveVoicePreferences({ wakeWordEnabled: !voicePrefs.wakeWordEnabled }))
          }
          onToggleAutoSpeak={() =>
            setVoicePrefs(
              saveVoicePreferences({
                autoSpeakResponses: !voicePrefs.autoSpeakResponses,
              }),
            )
          }
        />
        <ChatComposer
          disabled={false}
          streaming={isActive}
          selectedCourseId={course.id}
          text={
            voiceInput.interim
              ? `${composerText}${composerText ? " " : ""}${voiceInput.interim}`.trim()
              : composerText
          }
          onTextChange={setComposerText}
          onSend={(t) => send(t)}
          onCancel={cancel}
          voiceAvailable={voiceInput.available}
          voicePhase={voiceInput.phase}
          voiceError={voiceInput.error}
          onVoiceToggle={voiceInput.startListening}
          onVoiceStop={() => {
            voiceInput.stopListening();
            const spoken = voiceInput.transcript.trim();
            if (spoken) {
              setComposerText((prev) => (prev.trim() ? `${prev.trim()} ${spoken}` : spoken));
              voiceInput.resetTranscript();
            }
          }}
          autoSpeakEnabled={voicePrefs.autoSpeakResponses}
          onAutoSpeakToggle={() =>
            setVoicePrefs(
              saveVoicePreferences({
                autoSpeakResponses: !voicePrefs.autoSpeakResponses,
              }),
            )
          }
          voiceOutputAvailable={voiceOutput.available}
        />
      </div>
    </div>
  );
}
