import type { InstructorAiPolicy, CourseCloudPolicy } from "@/lib/product/course-ai-policy";
import type { AiProcessingMode, LocalModelTier } from "@/lib/product/ai-preferences";

/** Server-authoritative product settings shared with the backend API. */
export interface ProductSettings {
  version: number;
  focusCourseIds: string[];
  termHint: string | null;
  aiProcessingMode: AiProcessingMode;
  localModelTier: LocalModelTier;
  privacyCloudOptInAcknowledged: boolean;
  updatedAt: string;
}

export interface CourseAiPolicySettings {
  courseId: string;
  instructorPolicy: InstructorAiPolicy;
  cloudProcessing: CourseCloudPolicy;
  notes: string;
  updatedAt: string | null;
}

export type ReadinessComponent =
  | "backend"
  | "database"
  | "canvas"
  | "sync"
  | "local_ai_runtime"
  | "local_ai_model"
  | "document_index"
  | "privacy";

export type ReadinessStatus = "unknown" | "ready" | "degraded" | "unavailable" | "action_required";

export interface ReadinessCheck {
  component: ReadinessComponent;
  status: ReadinessStatus;
  label: string;
  detail: string | null;
  actionLabel: string | null;
}

export interface ProductReadiness {
  overall: ReadinessStatus;
  checks: ReadinessCheck[];
  updatedAt: string | null;
}

export interface CourseWorkspaceState {
  courseId: string;
  conversationId: string | null;
  lastViewedAt: string | null;
}

export type DisambiguationEntityKind = "course" | "assignment" | "document";

export interface DisambiguationCandidate {
  id: string;
  kind: DisambiguationEntityKind;
  title: string;
  subtitle: string | null;
  courseId: string | null;
}

export interface EntityDisambiguationRequest {
  text?: string;
  courseId?: string;
  assignmentId?: string;
  documentId?: string;
  intent?: string;
}

export interface EntityDisambiguationResult {
  outcome: "resolved" | "ambiguous" | "unresolved";
  kind: DisambiguationEntityKind | null;
  selectedId: string | null;
  candidates: DisambiguationCandidate[];
  reason: string | null;
}

export type DataLifecycleAction =
  | "clear_course_workspace"
  | "clear_assistant_context"
  | "clear_study_sessions"
  | "clear_practice_sessions"
  | "clear_local_index"
  | "disconnect_canvas";

export interface DataLifecycleRequest {
  action: DataLifecycleAction;
  courseId?: string;
  confirmToken: string;
}

export interface DataLifecycleResult {
  ok: boolean;
  message: string;
}

export const PRODUCT_SETTINGS_API_VERSION = 1;
