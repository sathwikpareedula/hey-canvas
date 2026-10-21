"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatMessageView } from "@/components/chat/ChatMessage";
import { AcademicContextBar } from "@/components/hey-canvas/AcademicContextBanner";
import { AssistantRuntimeStatus } from "@/components/hey-canvas/AssistantRuntimeStatus";
import { ContextModeBadge } from "@/components/product/ContextModeBadge";
import { EntityDisambiguationCard } from "@/components/product/EntityDisambiguationCard";
import {
  getProductSettingsApi,
  resolveEntitiesWithFallback,
} from "@/lib/api/product-settings-service";
import type { DisambiguationCandidate } from "@/lib/domain/product-settings";
import { HeyCanvasPlanningBar } from "@/components/hey-canvas/HeyCanvasPlanningBar";
import { StudyModeSelector } from "@/components/hey-canvas/StudyModeSelector";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useConversation } from "@/contexts/ConversationContext";
import { useCourseContext } from "@/contexts/CourseContext";
import { usePreferences } from "@/contexts/PreferencesContext";
import { useAssistantSession } from "@/hooks/useAssistantSession";
import { useHeyCanvasWakeWord } from "@/hooks/useHeyCanvasWakeWord";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useVoiceOutput } from "@/hooks/useVoiceOutput";
import { VoiceHandsFreeBar } from "@/components/voice/VoiceHandsFreeBar";
import {
  readVoicePreferences,
  saveVoicePreferences,
} from "@/lib/product/voice-preferences";
import { practiceAnswerRequest } from "@/lib/assistant/practice-chat";
import { MOCK_GREETING_HOUR } from "@/lib/api/mock/data";
import { presentAcademicError } from "@/lib/api/error-presentation";
import type { AssistantRequest } from "@/lib/domain/assistant";
import { parseStudyMode } from "@/lib/domain/study-mode";
import { buildHeyCanvasSuggestions } from "@/lib/hey-canvas/suggestions";
import {
  buildDeadlineFastPathMessage,
  matchDeadlineFastPath,
} from "@/lib/product/deadline-fast-path";
import {
  activeAssignmentIdFromMessages,
  activeDocumentIdFromMessages,
} from "@/lib/product/conversation-entity-context";
import type { Assignment, ChatMessage, Course } from "@/lib/domain/types";

export function HeyCanvasWorkspace() {
  const api = useAcademicApi();
  const { displayName } = usePreferences();
  const { courseId, setCourseId } = useCourseContext();
  const {
    conversation,
    conversationEpoch,
    messages,
    setMessages,
    startNewConversation,
    conversations,
    selectConversation,
  } = useConversation();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const productApi = useMemo(() => getProductSettingsApi(), []);
  const [disambiguation, setDisambiguation] = useState<{
    title: string;
    candidates: DisambiguationCandidate[];
    pendingPrompt: string;
    courseId?: string;
  } | null>(null);
  const studyMode = parseStudyMode(searchParams.get("studyMode"));
  const assignmentId = searchParams.get("assignmentId");
  const documentId = searchParams.get("documentId");
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [courseReloadKey, setCourseReloadKey] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [composerText, setComposerText] = useState("");
  const [voicePrefs, setVoicePrefs] = useState(() => readVoicePreferences());
  const autoSpeak = voicePrefs.autoSpeakResponses;
  const autoSpeakRef = useRef(autoSpeak);
  useEffect(() => {
    autoSpeakRef.current = autoSpeak;
  }, [autoSpeak]);
  const [contextTitles, setContextTitles] = useState<{
    assignment?: string;
    document?: string;
  }>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const voiceOutput = useVoiceOutput();
  const voiceInput = useVoiceInput();
  const wakeNotifyRef = useRef<(speaking: boolean) => void>(() => {});

  const {
    send: sendAssistant,
    isActive: assistantActive,
    streamingText,
    cancel: cancelAssistant,
    resetSession: resetAssistantSession,
    retryLast,
    clearPracticeSession,
    activityMessage,
  } = useAssistantSession({
    conversationId: conversation.id,
    conversationEpoch,
    onMessages: setMessages,
    onTransportError: setError,
    onAssistantMessage: (message) => {
      if (!autoSpeakRef.current) return;
      voiceInput.setPhase("speaking");
      wakeNotifyRef.current(true);
      voiceOutput.speakMessage(message, () => {
        wakeNotifyRef.current(false);
        voiceInput.setPhase("idle");
      });
    },
  });

  const sendRef = useRef<(text: string, courseIdOverride?: string) => void>(() => {});

  const coursesById = useMemo(() => new Map(courses.map((c) => [c.id, c])), [courses]);
  const courseName = courseId ? coursesById.get(courseId)?.name : null;
  const courseFromUrl = searchParams.get("courseId");

  useEffect(() => {
    if (courseFromUrl && courseFromUrl !== courseId) {
      setCourseId(courseFromUrl);
    }
  }, [courseFromUrl, courseId, setCourseId]);

  useEffect(() => {
    let active = true;
    api
      .getCourses()
      .then((c) => {
        if (active) setCourses(c);
      })
      .catch((err) => {
        if (active) setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, courseReloadKey]);

  useEffect(() => {
    if (!assignmentId && !documentId) return;
    let active = true;
    (async () => {
      const next: { assignment?: string; document?: string } = {};
      if (assignmentId) {
        const a = await api.getAssignment(assignmentId).catch(() => null);
        if (a) next.assignment = a.title;
      }
      if (documentId) {
        const d = await api.getDocument(documentId).catch(() => null);
        if (d) next.document = d.title;
      }
      if (active) setContextTitles(next);
    })();
    return () => {
      active = false;
    };
  }, [api, assignmentId, documentId]);

  const suggestions = useMemo(
    () =>
      buildHeyCanvasSuggestions({
        courseId,
        courseName,
        assignmentId,
        assignmentTitle: contextTitles.assignment,
        documentId,
        documentTitle: contextTitles.document,
        studyMode,
      }),
    [
      courseId,
      courseName,
      assignmentId,
      contextTitles.assignment,
      documentId,
      contextTitles.document,
      studyMode,
    ],
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({
      top: el.scrollHeight,
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [messages, streamingText, assistantActive]);

  const dispatchAssistant = useCallback(
    (request: AssistantRequest) => {
      voiceOutput.cancelSpeech();
      voiceInput.cancel();
      setError(null);
      void sendAssistant(request);
    },
    [sendAssistant, voiceInput, voiceOutput],
  );

  const dispatchPrompt = useCallback(
    (
      text: string,
      activeCourse?: string,
      ctx?: { assignmentId?: string; documentId?: string },
    ) => {
      const fastWindow = matchDeadlineFastPath(text);
      const aId = ctx?.assignmentId ?? assignmentId ?? undefined;
      const dId = ctx?.documentId ?? documentId ?? undefined;
      if (fastWindow && !aId && !dId && !studyMode) {
        setError(null);
        const userMsg: ChatMessage = {
          id: `u-${Date.now()}`,
          role: "user",
          createdAt: new Date().toISOString(),
          text,
        };
        setMessages((m) => [...m, userMsg]);
        void (async () => {
          try {
            const [deadlines, overdue, nextWeekAssignments] = await Promise.all([
              api.getDeadlines(),
              api.getAssignments({ window: "past_due_time", courseId: activeCourse }),
              fastWindow === "next_week"
                ? api.getAssignments(
                    activeCourse
                      ? { window: "next_week", courseId: activeCourse }
                      : { window: "next_week" },
                  )
                : Promise.resolve([] as Assignment[]),
            ]);
            const message = buildDeadlineFastPathMessage({
              window: fastWindow,
              deadlines,
              overdue,
              courseId: activeCourse,
              courses,
              allAssignments: fastWindow === "next_week" ? nextWeekAssignments : undefined,
            });
            setMessages((m) => [...m, message]);
          } catch (err) {
            setError(err);
          }
        })();
        setComposerText("");
        voiceInput.resetTranscript();
        return;
      }
      dispatchAssistant({
        prompt: text,
        courseId: activeCourse,
        assignmentId: aId,
        documentId: dId,
        studyMode: studyMode ?? undefined,
      });
      setComposerText("");
      voiceInput.resetTranscript();
    },
    [
      api,
      courses,
      dispatchAssistant,
      assignmentId,
      documentId,
      studyMode,
      voiceInput,
      setMessages,
    ],
  );

  const send = useCallback(
    (text: string, overrideCourseId?: string) => {
      const activeCourse = overrideCourseId ?? courseId ?? undefined;
      if (assignmentId || documentId) {
        dispatchPrompt(text, activeCourse);
        return;
      }
      if (matchDeadlineFastPath(text) && !studyMode) {
        dispatchPrompt(text, activeCourse);
        return;
      }
      void (async () => {
        const conversationalAssignmentId =
          assignmentId ?? activeAssignmentIdFromMessages(messages) ?? undefined;
        const conversationalDocumentId =
          documentId ?? activeDocumentIdFromMessages(messages) ?? undefined;
        const result = await resolveEntitiesWithFallback(productApi, api, {
          text,
          courseId: activeCourse,
          assignmentId: conversationalAssignmentId,
          documentId: conversationalDocumentId,
        });
        if (result.outcome === "ambiguous" && result.candidates.length) {
          setDisambiguation({
            title:
              result.kind === "assignment"
                ? "Which assignment did you mean?"
                : result.kind === "document"
                  ? "Which material did you mean?"
                  : "Which course did you mean?",
            candidates: result.candidates,
            pendingPrompt: text,
            courseId: activeCourse,
          });
          return;
        }
        if (result.outcome === "resolved" && result.kind === "course" && result.selectedId) {
          if (!activeCourse) setCourseId(result.selectedId);
          dispatchPrompt(text, result.selectedId);
          return;
        }
        if (result.outcome === "resolved" && result.kind === "assignment" && result.selectedId) {
          const params = new URLSearchParams(searchParams.toString());
          params.set("assignmentId", result.selectedId);
          if (activeCourse) params.set("courseId", activeCourse);
          router.replace(`${pathname}?${params.toString()}`);
          dispatchPrompt(text, activeCourse, { assignmentId: result.selectedId });
          return;
        }
        if (result.outcome === "resolved" && result.kind === "document" && result.selectedId) {
          const params = new URLSearchParams(searchParams.toString());
          params.set("documentId", result.selectedId);
          if (activeCourse) params.set("courseId", activeCourse);
          router.replace(`${pathname}?${params.toString()}`);
          dispatchPrompt(text, activeCourse, { documentId: result.selectedId });
          return;
        }
        dispatchPrompt(text, activeCourse);
      })();
    },
    [
      api,
      productApi,
      courseId,
      assignmentId,
      documentId,
      dispatchPrompt,
      setCourseId,
      studyMode,
      messages,
      pathname,
      router,
      searchParams,
    ],
  );

  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const wakeThinkingRef = useRef<() => void>(() => {});
  const wakeWord = useHeyCanvasWakeWord({
    enabled: voicePrefs.wakeWordEnabled,
    paused:
      assistantActive ||
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

  const onPickDisambiguation = useCallback(
    (candidate: DisambiguationCandidate) => {
      const prompt = disambiguation?.pendingPrompt ?? "";
      const activeCourse = disambiguation?.courseId ?? courseId ?? undefined;
      setDisambiguation(null);
      if (candidate.kind === "course") {
        setCourseId(candidate.id);
        dispatchPrompt(prompt, candidate.id);
        return;
      }
      const params = new URLSearchParams(searchParams.toString());
      if (candidate.kind === "assignment") {
        params.set("assignmentId", candidate.id);
        if (candidate.courseId) params.set("courseId", candidate.courseId);
        router.replace(`${pathname}?${params.toString()}`);
        dispatchPrompt(prompt, candidate.courseId ?? activeCourse, {
          assignmentId: candidate.id,
        });
        return;
      }
      params.set("documentId", candidate.id);
      if (candidate.courseId) params.set("courseId", candidate.courseId);
      router.replace(`${pathname}?${params.toString()}`);
      dispatchPrompt(prompt, candidate.courseId ?? activeCourse, {
        documentId: candidate.id,
      });
    },
    [
      disambiguation,
      courseId,
      setCourseId,
      dispatchPrompt,
      searchParams,
      pathname,
      router,
    ],
  );

  const handlePracticeAnswer = useCallback(
    (sessionId: string, answer: string) => {
      const activeCourse = courseId ?? undefined;
      dispatchAssistant({
        ...practiceAnswerRequest(sessionId, answer),
        courseId: activeCourse,
        assignmentId: assignmentId ?? undefined,
        documentId: documentId ?? undefined,
        studyMode: studyMode ?? undefined,
      });
    },
    [dispatchAssistant, courseId, assignmentId, documentId, studyMode],
  );

  const promptConsumed = useRef<string | null>(null);
  useEffect(() => {
    const prompt = searchParams.get("prompt");
    if (!prompt) {
      promptConsumed.current = null;
      return;
    }
    if (!loading && !assistantActive && promptConsumed.current !== prompt) {
      promptConsumed.current = prompt;
      send(prompt);
    }
  }, [loading, searchParams, send, assistantActive]);

  const greeting = useMemo(() => `Good ${MOCK_GREETING_HOUR()}, ${displayName}.`, [displayName]);

  const stopAndReset = () => {
    voiceOutput.cancelSpeech();
    voiceInput.cancel();
    if (assistantActive) cancelAssistant();
    resetAssistantSession();
    clearPracticeSession();
    startNewConversation();
    setComposerText("");
  };

  const handleCancel = () => {
    voiceOutput.cancelSpeech();
    voiceInput.cancel();
    cancelAssistant();
  };

  const thinking = assistantActive;
  const streamingPreview = streamingText || null;
  const transportNote = error ? presentAcademicError(error) : null;

  if (loading) return <PageSkeleton />;

  return (
    <div className="mx-auto flex min-h-0 min-w-0 max-w-5xl w-full flex-1 flex-col px-2 sm:px-4">
      <header className="mb-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold tracking-tight">Hey Canvas</h1>
          <ContextModeBadge
            course={courseId ? coursesById.get(courseId) ?? null : null}
            scoped={Boolean(courseId)}
          />
        </div>
        <p className="text-xs text-[var(--muted)]">
          Academic assistant for deadlines, materials, and study — grounded in your course context.
        </p>
        <AssistantRuntimeStatus />
      </header>
      <div className="mb-3 space-y-2">
        {disambiguation ? (
          <EntityDisambiguationCard
            title={disambiguation.title}
            candidates={disambiguation.candidates}
            onPick={onPickDisambiguation}
          />
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <AcademicContextBar courses={courses} />
          <div className="flex items-center gap-2">
            {conversations.length > 1 && (
              <select
                aria-label="Previous conversations"
                value={conversation.id}
                onChange={(e) => selectConversation(e.target.value)}
                className="max-w-[13rem] sm:max-w-xs truncate rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-xs text-[var(--foreground)] hover:border-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
              >
                {conversations.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.messages.length} msg{c.messages.length === 1 ? "" : "s"})
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              onClick={stopAndReset}
              className="shrink-0 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--surface-muted)] hover:border-[var(--accent)] transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            >
              + New conversation
            </button>
          </div>
        </div>
        <StudyModeSelector />
        {courseId && assignmentId ? (
          <HeyCanvasPlanningBar courseId={courseId} assignmentId={assignmentId} />
        ) : null}
      </div>
      {error && transportNote ? (
        <div className="mb-3">
          <ApiErrorPanel
            error={error}
            onRetry={
              transportNote.retryable
                ? () => {
                    setError(null);
                    if (transportNote.kind === "network") {
                      setLoading(true);
                      setCourseReloadKey((k) => k + 1);
                    } else {
                      retryLast();
                    }
                  }
                : undefined
            }
          />
        </div>
      ) : null}
      <div
        ref={scrollRef}
        className="flex-1 space-y-6 overflow-y-auto pr-1 pb-4"
        aria-live="polite"
        aria-busy={thinking}
      >
        {messages.length === 0 && !thinking ? (
          <div className="pt-4 text-center md:pt-8">
            <p className="text-lg font-medium">{greeting}</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Pick a suggestion or type a question. Context chips above show what Hey Canvas will
              use — nothing is submitted to Canvas automatically.
            </p>
            <ul className="mt-8 flex flex-wrap justify-center gap-2">
              {suggestions.map((prompt) => (
                <li key={prompt}>
                  <button
                    type="button"
                    onClick={() => send(prompt)}
                    disabled={thinking}
                    className="max-w-xs rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left text-sm hover:border-[var(--accent)] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
                  >
                    {prompt}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessageView
              key={msg.id}
              message={msg}
              coursesById={coursesById}
              onFollowUp={send}
              onPracticeAnswer={handlePracticeAnswer}
              practiceBusy={assistantActive}
              onRetry={msg.status === "error" ? retryLast : undefined}
            />
          ))
        )}
        {streamingPreview ? (
          <div
            className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface-muted)] px-4 py-3 text-sm whitespace-pre-wrap break-words text-[var(--muted)]"
            aria-live="polite"
            aria-busy="true"
          >
            {streamingPreview}
          </div>
        ) : null}
        {thinking && !streamingPreview ? (
          <p className="text-sm text-[var(--muted)]" role="status" aria-live="polite">
            {activityMessage ?? "Preparing your answer…"}
          </p>
        ) : null}
      </div>
      <div className="sticky bottom-0 border-t border-[var(--border)] bg-[var(--background)] pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <VoiceHandsFreeBar
          wakeEnabled={voicePrefs.wakeWordEnabled}
          wakeAvailable={wakeWord.available}
          wakePhase={wakeWord.phase}
          wakeLabel={wakeWord.label}
          autoSpeak={autoSpeak}
          autoSpeakAvailable={voiceOutput.available}
          onToggleWake={() =>
            setVoicePrefs(saveVoicePreferences({ wakeWordEnabled: !voicePrefs.wakeWordEnabled }))
          }
          onToggleAutoSpeak={() =>
            setVoicePrefs(
              saveVoicePreferences({ autoSpeakResponses: !voicePrefs.autoSpeakResponses }),
            )
          }
        />
        <ChatComposer
          disabled={false}
          streaming={assistantActive}
          selectedCourseId={courseId ?? ""}
          text={
            voiceInput.interim
              ? `${composerText}${composerText ? " " : ""}${voiceInput.interim}`.trim()
              : composerText
          }
          onTextChange={setComposerText}
          onSend={(text, cid) => send(text, cid)}
          onCancel={handleCancel}
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
          autoSpeakEnabled={autoSpeak}
          onAutoSpeakToggle={() =>
            setVoicePrefs(
              saveVoicePreferences({ autoSpeakResponses: !voicePrefs.autoSpeakResponses }),
            )
          }
          voiceOutputAvailable={voiceOutput.available}
        />
      </div>
    </div>
  );
}
