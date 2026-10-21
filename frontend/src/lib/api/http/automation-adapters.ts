import type { AutomationOperation, AutomationPreview, AutomationPreviewRequest } from "@/lib/domain/planning";

type BackendPreview = {
  operation: string;
  title: string;
  summary: string;
  payload?: Record<string, unknown> | null;
  requires_confirmation: boolean;
  safe_to_execute: boolean;
};

export function mapAutomationRequestToBackend(request: AutomationPreviewRequest) {
  return {
    operation: request.operation,
    course_id: request.courseId,
    assignment_id: request.assignmentId,
    query: request.query,
  };
}

export function mapBackendAutomationPreview(row: BackendPreview): AutomationPreview {
  return {
    operation: row.operation as AutomationOperation,
    title: row.title,
    summary: row.summary,
    payload:
      row.payload && typeof row.payload === "object"
        ? (row.payload as Record<string, unknown>)
        : null,
    requiresConfirmation: row.requires_confirmation,
    safeToExecute: row.safe_to_execute,
  };
}
