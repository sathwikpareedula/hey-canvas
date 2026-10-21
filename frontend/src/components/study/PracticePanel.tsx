"use client";

import { useEffect, useRef, useState } from "react";
import { EvidenceRefButton } from "@/components/study/EvidenceRefButton";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { PracticeSession } from "@/lib/domain/study-workflows";
import { practiceProgressLabel } from "@/lib/study/practice-present";

const PRACTICE_STORAGE_KEY = "hey-canvas-practice-session-id";

export function PracticePanel({
  courseId,
  initialTopic = "",
}: {
  courseId: string;
  initialTopic?: string;
}) {
  const api = useAcademicApi();
  const [topic, setTopic] = useState(initialTopic);
  const submitLock = useRef(false);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const activeSession = session?.courseId === courseId ? session : null;
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const storedId = localStorage.getItem(PRACTICE_STORAGE_KEY);
    if (!storedId) return;
    let active = true;
    api
      .getPracticeSession(storedId)
      .then((restored) => {
        if (!active) return;
        if (restored.courseId === courseId) setSession(restored);
        else localStorage.removeItem(PRACTICE_STORAGE_KEY);
      })
      .catch(() => localStorage.removeItem(PRACTICE_STORAGE_KEY));
    return () => {
      active = false;
    };
  }, [api, courseId]);

  const start = async () => {
    if (!topic.trim()) return;
    setBusy(true);
    setError(null);
    setFeedback(null);
    setHint(null);
    try {
      const created = await api.createPracticeSession(courseId, topic.trim());
      setSession(created);
      localStorage.setItem(PRACTICE_STORAGE_KEY, created.sessionId);
      setAnswer("");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!activeSession || answer.trim().length < 3 || busy || submitLock.current) return;
    submitLock.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerPracticeSession(activeSession.sessionId, answer.trim());
      setFeedback(result.feedback);
      setHint(result.hint);
      if (result.nextQuestion) {
        setSession({
          ...activeSession,
          question: result.nextQuestion,
          progress: result.progress,
          questionIndex: activeSession.questionIndex + 1,
          correctAnswers: activeSession.correctAnswers + (result.correct ? 1 : 0),
        });
        setAnswer("");
      } else {
        const refreshed = await api.getPracticeSession(activeSession.sessionId);
        setSession(refreshed);
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      submitLock.current = false;
    }
  };

  const requestHint = async () => {
    if (!activeSession || busy) return;
    setBusy(true);
    try {
      setHint(await api.hintPracticeSession(activeSession.sessionId));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-[var(--border)] p-4" aria-label="Practice mode">
      <h2 className="text-sm font-semibold">Practice</h2>
      <p className="text-xs text-[var(--muted)]">
        Generated practice only — not official Canvas quizzes. Answers stay on this device until
        submitted to the practice API for feedback.
      </p>
      {!activeSession ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Topic to practice"
            className="min-h-10 flex-1 rounded-lg border border-[var(--border)] px-3 text-sm"
            aria-label="Practice topic"
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => void start()}
            className="min-h-10 rounded-full bg-[var(--accent)] px-4 text-sm text-[var(--accent-fg)]"
          >
            Start practice
          </button>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-[var(--muted)]">{practiceProgressLabel(activeSession)}</p>
          {activeSession.question ? (
            <>
              <div className="rounded-xl bg-[var(--surface-muted)] p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  {activeSession.question.generated ? (
                    <span className="inline-flex items-center rounded-md bg-purple-50 dark:bg-purple-950/60 px-2 py-0.5 text-xs font-medium text-purple-700 dark:text-purple-300 ring-1 ring-inset ring-purple-600/20">
                      ✦ AI Practice (Generated)
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-md bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300 ring-1 ring-inset ring-emerald-600/20">
                      Official Source
                    </span>
                  )}
                  <span className="text-[11px] text-[var(--muted)]">Self-study practice only · Ungraded</span>
                </div>
                <p className="font-medium text-[var(--foreground)]">{activeSession.question.question}</p>
              </div>
              {activeSession.question.evidence.length ? (
                <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2.5">
                  <p className="text-xs font-semibold text-[var(--foreground)] flex items-center gap-1.5 mb-1.5">
                    <span>📖</span> Professor Course Evidence (Grounding):
                  </p>
                  <ul className="space-y-1">
                    {activeSession.question.evidence.map((ev, i) => (
                      <li key={i}>
                        <EvidenceRefButton evidence={ev} courseId={courseId} />
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="rounded-lg border border-[var(--border)]/70 bg-[var(--surface-muted)] p-2 text-xs text-[var(--muted)]">
                  Note: This question is generated for conceptual drill and is not directly cited from an indexed professor document.
                </p>
              )}
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    void submit();
                  }
                }}
                rows={4}
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
                aria-label="Your answer"
                aria-describedby="practice-submit-hint"
              />
              <p id="practice-submit-hint" className="text-[10px] text-[var(--muted)]">
                Ctrl+Enter to submit. Use multiple lines freely.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy || answer.trim().length < 3}
                  onClick={() => void submit()}
                  className="min-h-9 rounded-full bg-[var(--accent)] px-3 text-sm text-[var(--accent-fg)] disabled:opacity-50"
                >
                  {busy ? "Submitting…" : "Submit for feedback"}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void requestHint()}
                  className="min-h-9 rounded-full border border-[var(--border)] px-3 text-sm"
                >
                  Hint
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm">Practice session complete.</p>
          )}
          {feedback ? (
            <p className="text-sm" role="status" aria-live="polite">{feedback}</p>
          ) : null}
          {hint ? <p className="text-xs text-[var(--muted)]">Hint: {hint}</p> : null}
        </div>
      )}
      {error ? <ApiErrorPanel error={error} /> : null}
    </section>
  );
}
