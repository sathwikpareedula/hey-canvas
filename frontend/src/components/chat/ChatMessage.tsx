import { memo } from "react";
import { AssistantResponse } from "@/components/chat/AssistantResponse";
import { AcademicMarkdownView } from "@/components/chat/AcademicMarkdownView";
import type { ChatMessage as ChatMessageType, Course } from "@/lib/domain/types";
import { formatRelativeTime } from "@/lib/utils/date";

export const ChatMessageView = memo(function ChatMessageView({
  message,
  coursesById,
  onFollowUp,
  onPracticeAnswer,
  practiceBusy,
  onRetry,
}: {
  message: ChatMessageType;
  coursesById: Map<string, Course>;
  onFollowUp?: (prompt: string) => void;
  onPracticeAnswer?: (sessionId: string, answer: string) => void;
  practiceBusy?: boolean;
  onRetry?: () => void;
}) {
  const isUser = message.role === "user";
  const label = isUser ? "You" : "Hey Canvas";
  const interrupted = message.status === "incomplete_data";

  return (
    <article
      className={`flex gap-3.5 ${isUser ? "flex-row-reverse" : "flex-row"} w-full`}
      aria-label={`${label} message`}
    >
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold shadow-xs ${
          isUser
            ? "bg-[var(--accent)] text-[var(--accent-fg)]"
            : "border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--accent)]"
        }`}
        aria-hidden
      >
        {isUser ? "You" : "HC"}
      </div>
      <div className={`min-w-0 flex-1 ${isUser ? "text-right" : "text-left"}`}>
        <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
          <span className="font-medium text-[var(--foreground)]">{label}</span>
          <time dateTime={message.createdAt}>{formatRelativeTime(message.createdAt)}</time>
          {interrupted ? <span className="text-[var(--warn-text)]">Stopped</span> : null}
          {message.status === "error" && onRetry ? (
            <button type="button" className="underline hover:text-[var(--accent)]" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
        <div
          className={`inline-block w-full max-w-[min(100%,56rem)] rounded-2xl px-4 py-3.5 text-left shadow-xs transition ${
            isUser
              ? "bg-[var(--accent)] text-[var(--accent-fg)] font-medium"
              : "border border-[var(--border)] bg-[var(--surface)]"
          }`}
        >
          {message.text ? (
            isUser ? (
              <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{message.text}</p>
            ) : (
              <AcademicMarkdownView content={message.text} />
            )
          ) : null}
          {message.blocks?.length ? (
            <AssistantResponse
              blocks={message.blocks}
              coursesById={coursesById}
              onFollowUp={onFollowUp}
              onPracticeAnswer={onPracticeAnswer}
              practiceBusy={practiceBusy}
            />
          ) : null}
        </div>
      </div>
    </article>
  );
});
