import {
  mapBackendCalendarEvent,
  mapBackendCalendarExecution,
  mapBackendCalendarPreview,
} from "@/lib/api/http/calendar-adapters";
import { mapBackendNotificationList } from "@/lib/api/http/notification-adapters";
import { mapBackendReminderPreview } from "@/lib/api/http/reminder-adapters";
import type { BackendResponseBlock } from "@/lib/api/http/assistant-adapters";
import {
  mapBackendPracticeFeedback,
  mapBackendPracticeSession,
  mapBackendStudyGuide,
  mapBackendStudySession,
} from "@/lib/api/http/study-workflow-adapters";
import type { AssistantBlock } from "@/lib/domain/types";

type JsonRecord = Record<string, unknown>;

type BackendEventRow = {
  event_id: string;
  course_id: string;
  assignment_id?: string | null;
  summary: string;
  description?: string | null;
  start_at: string;
  end_at: string;
  all_day: boolean;
  status: string;
  source?: string;
  external_id?: string | null;
  provider: string;
};

export function mapStructuredAssistantBlock(block: BackendResponseBlock): AssistantBlock | null {
  const payload = block.payload;
  if (!payload || typeof payload !== "object") {
    if (block.text) return { type: "text", content: block.text };
    return null;
  }

  const row = payload as JsonRecord;

  switch (block.type) {
    case "practice_question":
      return {
        type: "practice_question",
        content: block.text ?? undefined,
        practiceSession: mapBackendPracticeSession(row),
      };
    case "practice_feedback":
      return {
        type: "practice_feedback",
        content: block.text ?? undefined,
        practiceFeedback: mapBackendPracticeFeedback(row),
      };
    case "study_plan":
      return {
        type: "study_plan",
        content: block.text ?? undefined,
        studySession: mapBackendStudySession(row),
      };
    case "study_guide":
      return {
        type: "study_guide",
        content: block.text ?? undefined,
        studyGuide: mapBackendStudyGuide(row),
      };
    case "notification_summary":
      return {
        type: "notification_summary",
        content: block.text ?? undefined,
        notificationItems: mapBackendNotificationList(
          row as Parameters<typeof mapBackendNotificationList>[0],
        ),
      };
    case "reminder_preview":
      return {
        type: "reminder_preview",
        content: block.text ?? undefined,
        reminderPreview: mapBackendReminderPreview(
          row as Parameters<typeof mapBackendReminderPreview>[0],
        ),
      };
    case "calendar_action_preview": {
      if ("event" in row && "confirmation" in row) {
        return {
          type: "calendar_action_preview",
          content: block.text ?? undefined,
          calendarPreview: mapBackendCalendarPreview(
            row as {
              event: BackendEventRow;
              confirmation: { action_id: string; confirmation_token: string };
            },
          ),
        };
      }
      return {
        type: "calendar_action_preview",
        content: block.text ?? undefined,
        calendarPreview: {
          event: mapBackendCalendarEvent(row as BackendEventRow),
          confirmation: { actionId: "assistant-preview", confirmationToken: "" },
        },
      };
    }
    case "calendar_action_result":
      return {
        type: "calendar_action_result",
        content: block.text ?? undefined,
        calendarResult: mapBackendCalendarExecution(
          row as Parameters<typeof mapBackendCalendarExecution>[0],
        ),
      };
    default:
      return null;
  }
}

export function extractPracticeSessionIdFromBlocks(
  blocks: AssistantBlock[] | undefined,
): string | undefined {
  if (!blocks?.length) return undefined;
  for (let i = blocks.length - 1; i >= 0; i -= 1) {
    const block = blocks[i];
    if (block?.type === "practice_question" && block.practiceSession?.sessionId) {
      return block.practiceSession.sessionId;
    }
  }
  return undefined;
}
