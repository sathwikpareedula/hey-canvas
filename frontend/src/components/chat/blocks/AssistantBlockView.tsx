import { AssignmentRow } from "@/components/assignment/AssignmentRow";
import { CourseBadge } from "@/components/course/CourseBadge";
import {
  ChatCalendarPreviewBlock,
  ChatCalendarResultBlock,
  ChatNotificationSummaryBlock,
  ChatReminderPreviewBlock,
  ChatStudyGuideBlock,
  ChatStudyPlanBlock,
} from "@/components/chat/blocks/ChatPlanningBlocks";
import {
  ChatPracticeFeedbackBlock,
  ChatPracticeQuestionBlock,
} from "@/components/chat/blocks/ChatPracticeBlock";
import { FollowUpChips } from "@/components/chat/blocks/FollowUpChips";
import { SourceCitationList } from "@/components/sources/SourceCitation";
import {
  deadlineEmptyMessageFromHint,
  sanitizeAssistantTextContent,
} from "@/lib/assistant/present-assistant-text";
import { sanitizeAssistantBlock } from "@/lib/assistant/normalize-block";
import type { AssistantBlock, Course } from "@/lib/domain/types";
import {
  formatChangeValue,
  humanizeChangeFieldName,
} from "@/lib/utils/chicago-date";
import { AcademicMarkdownView } from "@/components/chat/AcademicMarkdownView";
import { formatRelativeTime } from "@/lib/utils/date";

function TextBlock({ block }: { block: AssistantBlock }) {
  const content = sanitizeAssistantTextContent(block.content);
  if (!content) return null;
  const tone =
    block.type === "warning"
      ? "text-[var(--warn-text)]"
      : block.type === "error"
        ? "text-[var(--danger-text)]"
        : "text-[var(--foreground)]";
  return <AcademicMarkdownView content={content} className={tone} />;
}

export function DeadlineGroupBlock({
  assignments,
  coursesById,
  emptyMessage,
}: {
  assignments: AssistantBlock["assignments"];
  coursesById: Map<string, Course>;
  emptyMessage?: string;
}) {
  if (!assignments?.length) {
    if (!emptyMessage) return null;
    return (
      <p className="rounded-lg border border-dashed border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)]">
        {emptyMessage}
      </p>
    );
  }
  return (
    <section
      aria-label="Deadlines"
      className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3"
    >
      {assignments.map((a) => (
        <AssignmentRow
          key={a.id}
          assignment={a}
          course={coursesById.get(a.courseId)}
          compact
          href={`/assignments/${a.id}`}
        />
      ))}
    </section>
  );
}

export function AssignmentContextBlock({
  assignments,
  coursesById,
}: {
  assignments: AssistantBlock["assignments"];
  coursesById: Map<string, Course>;
}) {
  return <DeadlineGroupBlock assignments={assignments} coursesById={coursesById} />;
}

export function CourseContextBlock({ course }: { course?: Course }) {
  if (!course) return null;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
      <CourseBadge course={course} />
      <p className="mt-1 text-sm font-medium break-words">{course.name}</p>
    </div>
  );
}

export function StudyPlanBlock({ tips, title }: { tips?: string[]; title?: string }) {
  if (!tips?.length) return null;
  return (
    <section aria-label={title ?? "Study plan"} className="rounded-xl border border-[var(--border)] p-3">
      {title ? <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{title}</h4> : null}
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-[var(--foreground)]">
        {tips.map((tip, j) => (
          <li key={j} className="break-words">{tip}</li>
        ))}
      </ol>
    </section>
  );
}

export function MaterialEvidenceBlock({ sources }: { sources?: AssistantBlock["sources"] }) {
  if (!sources?.length) return null;
  return <SourceCitationList sources={sources} />;
}

export function RecentChangesBlock({ changes }: { changes?: AssistantBlock["changes"] }) {
  if (!changes?.length) return null;
  return (
    <ul className="space-y-2 text-sm">
      {changes.map((c) => (
        <li
          key={c.id}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
        >
          <p className="font-medium break-words">{c.entityLabel}</p>
          <p className="text-xs text-[var(--muted)]">
            {c.courseName ?? "Course"} · {c.eventType.replaceAll("_", " ")} ·{" "}
            {formatRelativeTime(c.observedAt)}
          </p>
          {c.fieldName && (c.oldValue || c.newValue) ? (
            <p className="mt-1 text-xs text-[var(--foreground)]">
              <span className="font-medium text-[var(--muted)]">
                {humanizeChangeFieldName(c.fieldName)} changed:{" "}
              </span>
              {c.oldValue ? <span>{formatChangeValue(c.oldValue)}</span> : null}
              {c.oldValue && c.newValue ? (
                <span className="text-[var(--muted)]"> → </span>
              ) : null}
              {c.newValue ? <span>{formatChangeValue(c.newValue)}</span> : null}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function WarningBlock({ content }: { content?: string }) {
  if (!content) return null;
  return (
    <p className="rounded-lg border border-[var(--warn-border)] bg-[var(--warn-bg)] px-3 py-2 text-sm text-[var(--warn-text)] break-words">
      {content}
    </p>
  );
}

export function ErrorBlock({ content }: { content?: string }) {
  if (!content) return null;
  return (
    <p className="rounded-lg border border-[var(--danger-border)] bg-[var(--danger-bg)] px-3 py-2 text-sm text-[var(--danger-text)] break-words">
      {content}
    </p>
  );
}

export function AssistantBlockView({
  block,
  coursesById,
  onFollowUp,
  onPracticeAnswer,
  practiceBusy,
  showFollowUps = true,
}: {
  block: AssistantBlock;
  coursesById: Map<string, Course>;
  onFollowUp?: (prompt: string) => void;
  onPracticeAnswer?: (sessionId: string, answer: string) => void;
  practiceBusy?: boolean;
  showFollowUps?: boolean;
}) {
  const safeBlock = sanitizeAssistantBlock(block);
  return (
    <div className="space-y-2.5 border-l-2 border-[var(--border)] pl-3 last:border-l-0 last:pl-0 only:border-l-0 only:pl-0">
      {safeBlock.type === "text" ? <TextBlock block={safeBlock} /> : null}
      {safeBlock.type === "warning" ? <WarningBlock content={safeBlock.content} /> : null}
      {safeBlock.type === "error" ? <ErrorBlock content={safeBlock.content} /> : null}
      {safeBlock.type === "deadlines" ? (
        <>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Canvas deadlines
          </p>
          <DeadlineGroupBlock
            assignments={safeBlock.assignments}
            coursesById={coursesById}
            emptyMessage={deadlineEmptyMessageFromHint(safeBlock.content)}
          />
        </>
      ) : null}
      {safeBlock.type === "assignment_summary" ? (
        <>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Canvas assignment context
          </p>
          {safeBlock.course ? <CourseContextBlock course={safeBlock.course} /> : null}
          <AssignmentContextBlock assignments={safeBlock.assignments} coursesById={coursesById} />
          {safeBlock.content ? <TextBlock block={safeBlock} /> : null}
        </>
      ) : null}
      {safeBlock.type === "course" ? <CourseContextBlock course={safeBlock.course} /> : null}
      {safeBlock.type === "study" ? (
        <>
          {safeBlock.content ? <TextBlock block={safeBlock} /> : null}
          <StudyPlanBlock tips={safeBlock.studyTips} title="Suggested approach" />
        </>
      ) : null}
      {safeBlock.type === "document_answer" ? (
        <>
          {safeBlock.content ? <TextBlock block={safeBlock} /> : null}
          {safeBlock.sources?.length ? (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                Evidence from course materials
              </p>
              <MaterialEvidenceBlock sources={safeBlock.sources} />
            </>
          ) : (
            <p className="text-xs text-[var(--muted)]">No material evidence was attached to this answer.</p>
          )}
        </>
      ) : null}
      {safeBlock.type === "changes_summary" ? (
        <>
          {safeBlock.content ? <TextBlock block={safeBlock} /> : null}
          <RecentChangesBlock changes={safeBlock.changes} />
        </>
      ) : null}
      {safeBlock.type === "study_plan" && safeBlock.studySession ? (
        <ChatStudyPlanBlock session={safeBlock.studySession} />
      ) : null}
      {safeBlock.type === "practice_question" && safeBlock.practiceSession ? (
        <ChatPracticeQuestionBlock
          session={safeBlock.practiceSession}
          onSubmitAnswer={(id, answer) => onPracticeAnswer?.(id, answer)}
          busy={practiceBusy}
        />
      ) : null}
      {safeBlock.type === "practice_feedback" && safeBlock.practiceFeedback ? (
        <ChatPracticeFeedbackBlock feedback={safeBlock.practiceFeedback} />
      ) : null}
      {safeBlock.type === "study_guide" && safeBlock.studyGuide ? (
        <ChatStudyGuideBlock
          guide={safeBlock.studyGuide}
          courseId={coursesById.size === 1 ? [...coursesById.keys()][0] : undefined}
        />
      ) : null}
      {safeBlock.type === "notification_summary" && safeBlock.notificationItems ? (
        <ChatNotificationSummaryBlock items={safeBlock.notificationItems} />
      ) : null}
      {safeBlock.type === "reminder_preview" && safeBlock.reminderPreview ? (
        <ChatReminderPreviewBlock preview={safeBlock.reminderPreview} />
      ) : null}
      {safeBlock.type === "calendar_action_preview" && safeBlock.calendarPreview ? (
        <ChatCalendarPreviewBlock preview={safeBlock.calendarPreview} />
      ) : null}
      {safeBlock.type === "calendar_action_result" && safeBlock.calendarResult ? (
        <ChatCalendarResultBlock result={safeBlock.calendarResult} />
      ) : null}
      {showFollowUps ? (
        <FollowUpChips items={safeBlock.followUps} onSelect={onFollowUp} />
      ) : null}
    </div>
  );
}
