import type { AssistantTransportRequest } from "@/lib/assistant/request-mapper";
import type { AssistantTransportEvent } from "@/lib/assistant/stream-events";
import type { StudyMode } from "@/lib/domain/study-mode";
import type { AssistantBlock, AssistantSource, ChatMessage } from "@/lib/domain/types";
import { mapPromptToAssistantQuery } from "@/lib/api/http/contract-mappings";
import {
  mapAssignmentContextPayload,
  mapDeadlineGroupPayload,
  mapDocumentEvidenceFromRecord,
  mapEvidenceReferences,
  mapRecentChangesPayload,
} from "@/lib/api/http/assistant-block-payloads";
import { presentAssistantStreamError } from "@/lib/api/assistant-stream-errors";
import { withEmptyResponseRecovery } from "@/lib/assistant/empty-response";
import { sanitizeAssistantTextContent } from "@/lib/assistant/present-assistant-text";
import { mapStructuredAssistantBlock } from "@/lib/api/http/assistant-structured-blocks";
import { mapBackendStudySession } from "@/lib/api/http/study-workflow-adapters";

export function mapUiStudyModeToAssistantBackend(mode: StudyMode): string {
  if (mode === "exam") return "exam_prep";
  return mode;
}

export interface BackendAssistantRequestBody {
  query: string;
  course_id?: string;
  assignment_id?: string;
  document_id?: string;
  study_mode?: string;
  session_id?: string;
  practice_session_id?: string;
  answer?: string;
  operation: string;
}

export function mapTransportRequestToBackendBody(
  request: AssistantTransportRequest,
): BackendAssistantRequestBody {
  const body: BackendAssistantRequestBody = {
    query: mapPromptToAssistantQuery(request.query),
    operation: "answer",
  };
  if (request.courseId) body.course_id = request.courseId;
  if (request.assignmentId) body.assignment_id = request.assignmentId;
  if (request.documentId) body.document_id = request.documentId;
  if (request.conversationId) body.session_id = request.conversationId;
  const study =
    request.backendStudyMode ??
    (request.studyMode ? mapUiStudyModeToAssistantBackend(request.studyMode) : undefined);
  if (study) body.study_mode = study;
  if (request.practiceSessionId) body.practice_session_id = request.practiceSessionId;
  if (request.answer) body.answer = request.answer;
  if (request.operation) body.operation = request.operation;
  return body;
}

export type BackendResponseBlock = {
  type: string;
  text?: string | null;
  payload?: Record<string, unknown> | null;
  references?: { authority: string; identifier: string; locator?: string | null }[];
};

type BackendAssistantResponse = {
  status: string;
  blocks?: BackendResponseBlock[];
  course_id?: string | null;
};

export function mapBackendSsePayloadToTransportEvents(
  sseEvent: string,
  data: Record<string, unknown>,
): AssistantTransportEvent[] {
  const type = (data.type as string | undefined) ?? sseEvent;
  switch (type) {
    case "started":
      return [
        {
          type: "start",
          conversationId: typeof data.session_id === "string" ? data.session_id : undefined,
        },
      ];
    case "text_delta":
      return typeof data.text === "string" ? [{ type: "text_delta", delta: data.text }] : [];
    case "warning":
      return typeof data.text === "string" ? [{ type: "warning", message: data.text }] : [];
    case "error":
      return [
        {
          type: "error",
          message: presentAssistantStreamError(
            typeof data.text === "string" ? data.text : "Assistant error",
          ),
          retryable: classifyAssistantErrorRetryable(data.text),
        },
      ];
    case "follow_up": {
      const suggestions = extractFollowUpSuggestions(data);
      return suggestions.length ? [{ type: "follow_up", suggestions }] : [];
    }
    case "source":
      if (typeof data.identifier !== "string") return [];
      return [
        {
          type: "source",
          source: mapSourceEventData(data),
        },
      ];
    case "block": {
      const block = mapBackendResponseBlock({
        type: (data.block_type as string) ?? "text",
        text: typeof data.text === "string" ? data.text : null,
        payload: (data.payload as Record<string, unknown> | null) ?? null,
        references: (data.references as BackendResponseBlock["references"]) ?? [],
      });
      return block ? [{ type: "block", block }] : [];
    }
    case "completed": {
      const response = data.response as BackendAssistantResponse | undefined;
      if (!response) {
        return [{ type: "error", message: "Assistant completed without a response.", retryable: true }];
      }
      return [{ type: "complete", message: mapBackendAssistantResponseToChatMessage(response) }];
    }
    default:
      return [{ type: "warning", message: `Ignored unsupported assistant event: ${type}` }];
  }
}

function classifyAssistantErrorRetryable(text: unknown): boolean {
  const message = String(text ?? "").toLowerCase();
  if (message.includes("disconnected")) return false;
  if (message.includes("ambiguous")) return false;
  if (message.includes("could not be resolved")) return false;
  if (message.includes("unsupported")) return false;
  if (message.includes("provider failed") || message.includes("unavailable")) return true;
  return true;
}

function extractFollowUpSuggestions(data: Record<string, unknown>): string[] {
  const payload = data.payload;
  if (payload && typeof payload === "object" && Array.isArray((payload as Record<string, unknown>).suggestions)) {
    return ((payload as Record<string, unknown>).suggestions as unknown[]).filter(
      (s): s is string => typeof s === "string",
    );
  }
  if (typeof data.text === "string" && data.text.trim()) return [data.text];
  return [];
}

function mapSourceEventData(data: Record<string, unknown>): AssistantSource {
  const payload = data.payload;
  if (payload && typeof payload === "object") {
    const mapped = mapDocumentEvidenceFromRecord(payload as Record<string, unknown>);
    if (mapped) return mapped;
  }
  const id = String(data.identifier ?? "source");
  const authority = typeof data.source === "string" ? data.source : "professor_material";
  const courseId = typeof data.course_id === "string" ? data.course_id : "";
  return {
    id,
    provenance: {
      courseId,
      courseName: courseId ? "Course" : "Unknown course",
      documentId: authority === "professor_material" ? id : undefined,
      documentTitle: "Course source",
      isStale: false,
    },
  };
}

export function mapBackendResponseBlock(block: BackendResponseBlock): AssistantBlock | null {
  const payload = block.payload ?? undefined;
  switch (block.type) {
    case "text": {
      const content = sanitizeAssistantTextContent(block.text ?? "");
      if (!content) return null;
      return { type: "text", content };
    }
    case "warning":
      return { type: "warning", content: block.text ?? "" };
    case "error":
      return { type: "error", content: block.text ?? "" };
    case "follow_up":
      return {
        type: "text",
        content: block.text ?? "",
        followUps: extractFollowUpsFromBlock(block),
      };
    case "deadline_group": {
      const assignments = mapDeadlineGroupPayload(payload);
      const windowHint =
        typeof payload?.window === "string"
          ? String(payload.window)
          : typeof block.text === "string"
            ? block.text
            : undefined;
      return {
        type: "deadlines",
        content: windowHint ?? block.text ?? undefined,
        assignments,
      };
    }
    case "assignment_context": {
      const ctx = mapAssignmentContextPayload(payload);
      return {
        type: "assignment_summary",
        content: block.text ?? ctx.summary,
        assignments: ctx.assignments,
        course: ctx.course,
      };
    }
    case "study_plan": {
      const structured = mapStructuredAssistantBlock(block);
      if (structured) return structured;
      if (payload && typeof payload === "object" && "session_id" in payload) {
        return {
          type: "study_plan",
          content: block.text ?? undefined,
          studySession: mapBackendStudySession(payload as Record<string, unknown>),
        };
      }
      return {
        type: "study",
        content: block.text ?? undefined,
        studyTips: extractStringList(payload, "tips"),
      };
    }
    case "practice_question":
    case "practice_feedback":
    case "study_guide":
    case "notification_summary":
    case "reminder_preview":
    case "calendar_action_preview":
    case "calendar_action_result": {
      const structured = mapStructuredAssistantBlock(block);
      if (structured) return structured;
      return { type: "text", content: block.text ?? "Structured response received." };
    }
    case "document_evidence": {
      const evidenceRows = Array.isArray(payload?.evidence)
        ? (payload!.evidence as Record<string, unknown>[])
        : undefined;
      const sources = mapEvidenceReferences(block.references, evidenceRows);
      return {
        type: "document_answer",
        content: block.text ?? undefined,
        sources: sources.length ? sources : undefined,
      };
    }
    case "recent_changes":
      return {
        type: "changes_summary",
        content: block.text ?? undefined,
        changes: mapRecentChangesPayload(payload),
      };
    default:
      return {
        type: "text",
        content: block.text ?? "",
      };
  }
}

function extractFollowUpsFromBlock(block: BackendResponseBlock): string[] | undefined {
  const fromPayload = extractStringList(block.payload, "suggestions");
  if (fromPayload?.length) return fromPayload;
  return block.text ? [block.text] : undefined;
}

function extractStringList(
  payload: Record<string, unknown> | null | undefined,
  key: string,
): string[] | undefined {
  const value = payload?.[key];
  if (!Array.isArray(value)) return undefined;
  return value.filter((v): v is string => typeof v === "string");
}

export function mapBackendAssistantResponseToChatMessage(
  response: BackendAssistantResponse,
): ChatMessage {
  const blocks =
    response.blocks
      ?.map((b) => mapBackendResponseBlock(b))
      .filter((b): b is AssistantBlock => b !== null) ?? [];
  const status = response.status === "ok" ? "complete" : "error";
  const message: ChatMessage = {
    id: `asst-${Date.now()}`,
    role: "assistant",
    createdAt: new Date().toISOString(),
    status,
    blocks: blocks.length ? blocks : [],
  };
  return withEmptyResponseRecovery(message);
}
