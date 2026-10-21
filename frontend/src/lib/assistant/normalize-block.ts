import { sanitizeAssistantTextContent } from "@/lib/assistant/present-assistant-text";
import type { AssistantBlock, AssistantBlockType } from "@/lib/domain/types";
import type { PracticeSession, StudySession } from "@/lib/domain/study-workflows";
import { finiteNumber, finitePercent } from "@/lib/utils/numbers";
import { displayOptionalText, displayText } from "@/lib/utils/display-text";

const KNOWN_BLOCK_TYPES: AssistantBlockType[] = [
  "text",
  "deadlines",
  "assignment_summary",
  "course",
  "study",
  "study_plan",
  "document_answer",
  "changes_summary",
  "practice_question",
  "practice_feedback",
  "study_guide",
  "notification_summary",
  "reminder_preview",
  "calendar_action_preview",
  "calendar_action_result",
  "warning",
  "error",
];

export function isKnownAssistantBlockType(type: string): type is AssistantBlockType {
  return KNOWN_BLOCK_TYPES.includes(type as AssistantBlockType);
}

function sanitizePracticeSession(session: PracticeSession): PracticeSession {
  return {
    ...session,
    sessionId: displayText(session.sessionId, "practice"),
    courseId: displayText(session.courseId, ""),
    topic: displayText(session.topic, "Practice"),
    questionIndex: finiteNumber(session.questionIndex, 0),
    totalQuestions: Math.max(finiteNumber(session.totalQuestions, 1), 1),
    correctAnswers: finiteNumber(session.correctAnswers, 0),
    progress: finitePercent(session.progress, 0),
    question: session.question
      ? {
          ...session.question,
          question: displayText(session.question.question, "Question unavailable."),
        }
      : null,
  };
}

function sanitizeStudySession(session: StudySession): StudySession {
  return {
    ...session,
    sessionId: displayText(session.sessionId, ""),
    courseId: displayText(session.courseId, ""),
    goal: displayText(session.goal, "Study plan"),
    durationMinutes: finiteNumber(session.durationMinutes, 45),
    progress: finitePercent(session.progress, 0),
    steps: session.steps.map((step) => ({
      ...step,
      title: displayText(step.title, "Step"),
      minutes: finiteNumber(step.minutes, 15),
      order: finiteNumber(step.order, 1),
    })),
  };
}

function sanitizeContentField(content?: string): string | undefined {
  const cleaned = sanitizeAssistantTextContent(content);
  if (!cleaned) return undefined;
  const out = displayText(cleaned, "");
  return out || undefined;
}

/** Fail safe on unknown backend block types without crashing the UI. */
export function sanitizeAssistantBlock(block: AssistantBlock): AssistantBlock {
  if (!isKnownAssistantBlockType(block.type)) {
    return {
      type: "warning",
      content: "This part of the response used an unsupported format and was omitted.",
    };
  }

  const base: AssistantBlock = {
    ...block,
    content: sanitizeContentField(block.content),
    followUps: block.followUps
      ?.map((f) => displayOptionalText(f))
      .filter((f): f is string => Boolean(f)),
    studyTips: block.studyTips
      ?.map((t) => displayOptionalText(t))
      .filter((t): t is string => Boolean(t)),
  };

  if (base.course) {
    base.course = {
      ...base.course,
      id: displayText(base.course.id, ""),
      name: displayText(base.course.name, "Course"),
      code: displayOptionalText(base.course.code),
    };
  }

  if (base.studySession) {
    base.studySession = sanitizeStudySession(base.studySession);
  }
  if (base.practiceSession) {
    base.practiceSession = sanitizePracticeSession(base.practiceSession);
  }
  if (base.practiceFeedback) {
    base.practiceFeedback = {
      ...base.practiceFeedback,
      feedback: displayText(base.practiceFeedback.feedback, ""),
      hint: base.practiceFeedback.hint
        ? displayText(base.practiceFeedback.hint, "")
        : null,
      progress: finitePercent(base.practiceFeedback.progress, 0),
    };
  }
  if (base.changes) {
    base.changes = base.changes.map((c) => ({
      ...c,
      entityLabel: displayText(c.entityLabel, "Update"),
      courseName: c.courseName ? displayText(c.courseName, "Course") : undefined,
      fieldName: c.fieldName ? displayText(c.fieldName, "") : null,
      oldValue: c.oldValue ? displayText(c.oldValue, "") : null,
      newValue: c.newValue ? displayText(c.newValue, "") : null,
    }));
  }
  if (base.notificationItems) {
    base.notificationItems = base.notificationItems.map((n) => ({
      ...n,
      title: displayText(n.title, "Notification"),
      body: displayText(n.body, ""),
    }));
  }

  return base;
}
