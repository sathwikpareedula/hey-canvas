"use client";

import { useRef, useState } from "react";
import { EvidenceRefButton } from "@/components/study/EvidenceRefButton";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { PracticeFeedback, PracticeSession } from "@/lib/domain/study-workflows";
import { practiceProgressLabel, practiceTopicLabel } from "@/lib/study/practice-present";

export function ChatPracticeQuestionBlock({
  session,
  onSubmitAnswer,
  busy,
}: {
  session: PracticeSession;
  onSubmitAnswer: (sessionId: string, answer: string) => void;
  busy?: boolean;
}) {
  const api = useAcademicApi();
  const [answer, setAnswer] = useState("");
  const [localHint, setLocalHint] = useState<string | null>(null);
  const [hintBusy, setHintBusy] = useState(false);
  const submitLock = useRef(false);

  const question = session.question?.question;

  const fetchHint = async () => {
    setHintBusy(true);
    try {
      const hint = await api.hintPracticeSession(session.sessionId);
      setLocalHint(hint);
    } catch {
      setLocalHint("Could not load a hint right now.");
    } finally {
      setHintBusy(false);
    }
  };

  const submit = () => {
    const trimmed = answer.trim();
    if (!trimmed || busy || submitLock.current) return;
    if (trimmed.length < 3) return;
    submitLock.current = true;
    onSubmitAnswer(session.sessionId, trimmed);
    setAnswer("");
    window.setTimeout(() => {
      submitLock.current = false;
    }, 800);
  };

  return (
    <section
      aria-label="Practice question"
      className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 space-y-2"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
        Practice · {practiceTopicLabel(session.topic)}
      </p>
      {question ? (
        <p className="text-sm font-medium break-words">{question}</p>
      ) : (
        <p className="text-sm text-[var(--muted)]">No question loaded.</p>
      )}
      {session.question?.evidence?.length ? (
        <ul className="flex flex-wrap gap-2">
          {session.question.evidence.map((ref) => (
            <li key={`${ref.authority}-${ref.identifier}`}>
              <EvidenceRefButton evidence={ref} courseId={session.courseId} />
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-xs text-[var(--muted)]">{practiceProgressLabel(session)}</p>
      {localHint ? (
        <p className="rounded-lg bg-[var(--surface-muted)] px-2 py-1.5 text-sm" role="status">
          {localHint}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={hintBusy || busy}
          onClick={() => void fetchHint()}
          className="min-h-9 rounded-full border border-[var(--border)] px-3 text-xs"
        >
          {hintBusy ? "Loading hint…" : "Hint"}
        </button>
      </div>
      <label className="block text-xs text-[var(--muted)]">
        Your answer
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          disabled={busy}
          rows={3}
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1.5 text-sm"
        />
      </label>
      <button
        type="button"
        disabled={busy || answer.trim().length < 3}
        onClick={submit}
        className="min-h-9 rounded-full bg-[var(--accent)] px-4 text-xs font-medium text-[var(--accent-fg)] disabled:opacity-50"
      >
        Check answer
      </button>
    </section>
  );
}

export function ChatPracticeFeedbackBlock({ feedback }: { feedback: PracticeFeedback }) {
  return (
    <section
      aria-label="Practice feedback"
      className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3 space-y-2"
    >
      <p
        className={`text-sm font-semibold ${feedback.correct ? "text-[var(--success-text,var(--foreground))]" : "text-[var(--warn-text)]"}`}
        role="status"
      >
        {feedback.correct ? "Correct" : "Keep going"}
      </p>
      <p className="text-sm break-words">{feedback.feedback}</p>
      {feedback.hint ? (
        <p className="text-sm text-[var(--muted)]">Hint: {feedback.hint}</p>
      ) : null}
      {feedback.nextQuestion ? (
        <p className="text-sm font-medium break-words">Next: {feedback.nextQuestion.question}</p>
      ) : null}
      <p className="text-xs text-[var(--muted)]">Progress {feedback.progress}%</p>
    </section>
  );
}
