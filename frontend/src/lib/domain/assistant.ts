import type { StudyMode } from "@/lib/domain/study-mode";
import type { AssistantBlock, AssistantSource, ChatMessage } from "@/lib/domain/types";

export type AssistantStatus =
  | "idle"
  | "thinking"
  | "streaming"
  | "complete"
  | "error"
  | "incomplete_data";

export interface AssistantRequest {
  prompt: string;
  courseId?: string;
  conversationId?: string;
  assignmentId?: string;
  documentId?: string;
  studyMode?: StudyMode;
  practiceSessionId?: string;
  answer?: string;
  operation?: string;
}

export interface AssistantResponse {
  message: ChatMessage;
  status: AssistantStatus;
  sources?: AssistantSource[];
}

/** Stream-capable boundary for a future provider-neutral assistant API. */
export type AssistantStreamEvent =
  | { type: "status"; status: AssistantStatus }
  | { type: "block"; block: AssistantBlock }
  | { type: "text_delta"; delta: string }
  | { type: "done"; message: ChatMessage }
  | { type: "error"; message: string };

export interface AssistantClient {
  ask(request: AssistantRequest): Promise<AssistantResponse>;
  stream?(request: AssistantRequest): AsyncIterable<AssistantStreamEvent>;
}
