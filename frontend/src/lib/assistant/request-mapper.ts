import type { AssistantRequest } from "@/lib/domain/assistant";
import { mapUiStudyModeToAssistantBackend } from "@/lib/api/http/assistant-adapters";
import { mapPromptToAssistantQuery } from "@/lib/api/http/contract-mappings";
import type { StudyMode } from "@/lib/domain/study-mode";

export interface AssistantTransportRequest {
  /** Wire format may use `query`; UI uses prompt. */
  query: string;
  courseId?: string;
  conversationId?: string;
  assignmentId?: string;
  documentId?: string;
  studyMode?: StudyMode;
  backendStudyMode?: string;
  practiceSessionId?: string;
  answer?: string;
  operation?: string;
}

export function mapUiRequestToTransport(
  request: AssistantRequest,
): AssistantTransportRequest {
  return {
    query: mapPromptToAssistantQuery(request.prompt),
    courseId: request.courseId,
    conversationId: request.conversationId,
    assignmentId: request.assignmentId,
    documentId: request.documentId,
    studyMode: request.studyMode,
    backendStudyMode: request.studyMode
      ? mapUiStudyModeToAssistantBackend(request.studyMode)
      : undefined,
    practiceSessionId: request.practiceSessionId,
    answer: request.answer,
    operation: request.operation,
  };
}

export function mapTransportToAcademicApiRequest(
  request: AssistantTransportRequest,
): AssistantRequest {
  return {
    prompt: request.query,
    courseId: request.courseId,
    conversationId: request.conversationId,
    assignmentId: request.assignmentId,
    documentId: request.documentId,
    studyMode: request.studyMode,
    practiceSessionId: request.practiceSessionId,
    answer: request.answer,
    operation: request.operation,
  };
}
