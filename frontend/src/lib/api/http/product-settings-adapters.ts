import type {
  CourseAiPolicySettings,
  CourseWorkspaceState,
  DisambiguationCandidate,
  EntityDisambiguationResult,
  ProductReadiness,
  ProductSettings,
  ReadinessCheck,
} from "@/lib/domain/product-settings";
import { PRODUCT_SETTINGS_API_VERSION } from "@/lib/domain/product-settings";

function pickString(row: Record<string, unknown>, key: string): string | null {
  const v = row[key];
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

export function mapBackendProductSettings(row: Record<string, unknown>): ProductSettings {
  return {
    version: typeof row.version === "number" ? row.version : PRODUCT_SETTINGS_API_VERSION,
    focusCourseIds: Array.isArray(row.focus_course_ids)
      ? row.focus_course_ids.filter((id): id is string => typeof id === "string")
      : Array.isArray(row.focusCourseIds)
        ? row.focusCourseIds.filter((id): id is string => typeof id === "string")
        : [],
    termHint: pickString(row, "term_hint") ?? pickString(row, "termHint"),
    aiProcessingMode:
      row.ai_processing_mode === "cloud" || row.aiProcessingMode === "cloud" ? "cloud" : "local",
    localModelTier:
      row.local_model_tier === "lightweight" || row.localModelTier === "lightweight"
        ? "lightweight"
        : row.local_model_tier === "higher_quality" || row.localModelTier === "higher_quality"
          ? "higher_quality"
          : "recommended",
    privacyCloudOptInAcknowledged: Boolean(
      row.privacy_cloud_opt_in_acknowledged ?? row.privacyCloudOptInAcknowledged,
    ),
    updatedAt:
      pickString(row, "updated_at") ?? pickString(row, "updatedAt") ?? new Date().toISOString(),
  };
}

export function mapProductSettingsToBackend(settings: ProductSettings): Record<string, unknown> {
  return {
    version: settings.version,
    focus_course_ids: settings.focusCourseIds,
    term_hint: settings.termHint,
    ai_processing_mode: settings.aiProcessingMode,
    local_model_tier: settings.localModelTier,
    privacy_cloud_opt_in_acknowledged: settings.privacyCloudOptInAcknowledged,
    updated_at: settings.updatedAt,
  };
}

export function mapBackendCoursePolicy(row: Record<string, unknown>): CourseAiPolicySettings {
  const instructor = row.instructor_policy ?? row.instructorPolicy;
  const cloud = row.cloud_processing ?? row.cloudProcessing;
  return {
    courseId: String(row.course_id ?? row.courseId ?? ""),
    instructorPolicy:
      instructor === "allowed" ||
      instructor === "restricted" ||
      instructor === "disabled"
        ? instructor
        : "unknown",
    cloudProcessing: cloud === "allowed" ? "allowed" : "local_only",
    notes: typeof row.notes === "string" ? row.notes : "",
    updatedAt: pickString(row, "updated_at") ?? pickString(row, "updatedAt"),
  };
}

export function mapCoursePolicyToBackend(policy: CourseAiPolicySettings): Record<string, unknown> {
  return {
    course_id: policy.courseId,
    instructor_policy: policy.instructorPolicy,
    cloud_processing: policy.cloudProcessing,
    notes: policy.notes,
    updated_at: policy.updatedAt,
  };
}

function mapReadinessCheck(row: Record<string, unknown>): ReadinessCheck {
  const component = String(row.component ?? "backend") as ReadinessCheck["component"];
  const status = String(row.status ?? "unknown") as ReadinessCheck["status"];
  return {
    component,
    status,
    label: typeof row.label === "string" ? row.label : "Status",
    detail: pickString(row, "detail"),
    actionLabel: pickString(row, "action_label") ?? pickString(row, "actionLabel"),
  };
}

export function mapBackendReadiness(row: Record<string, unknown>): ProductReadiness {
  const checks = Array.isArray(row.checks)
    ? row.checks.map((c) => mapReadinessCheck(c as Record<string, unknown>))
    : [];
  return {
    overall: (row.overall as ProductReadiness["overall"]) ?? "unknown",
    checks,
    updatedAt: pickString(row, "updated_at") ?? pickString(row, "updatedAt"),
  };
}

export function mapBackendWorkspace(row: Record<string, unknown>): CourseWorkspaceState {
  return {
    courseId: String(row.course_id ?? row.courseId ?? ""),
    conversationId: pickString(row, "conversation_id") ?? pickString(row, "conversationId"),
    lastViewedAt: pickString(row, "last_viewed_at") ?? pickString(row, "lastViewedAt"),
  };
}

export function mapWorkspaceToBackend(workspace: CourseWorkspaceState): Record<string, unknown> {
  return {
    course_id: workspace.courseId,
    conversation_id: workspace.conversationId,
    last_viewed_at: workspace.lastViewedAt,
  };
}

function mapCandidate(row: Record<string, unknown>): DisambiguationCandidate {
  const kind = String(row.kind ?? row.type ?? "course") as DisambiguationCandidate["kind"];
  return {
    id: String(row.id ?? ""),
    kind: kind === "assignment" || kind === "document" ? kind : "course",
    title: typeof row.title === "string" ? row.title : "Item",
    subtitle: pickString(row, "subtitle"),
    courseId: pickString(row, "course_id") ?? pickString(row, "courseId"),
  };
}

export function mapBackendDisambiguation(row: Record<string, unknown>): EntityDisambiguationResult {
  const candidates = Array.isArray(row.candidates)
    ? row.candidates.map((c) => mapCandidate(c as Record<string, unknown>))
    : [];
  const outcome = String(row.outcome ?? "unresolved") as EntityDisambiguationResult["outcome"];
  const kind = row.kind ?? row.entity_kind;
  return {
    outcome: outcome === "resolved" || outcome === "ambiguous" ? outcome : "unresolved",
    kind:
      kind === "assignment" || kind === "document" || kind === "course"
        ? kind
        : candidates[0]?.kind ?? null,
    selectedId: pickString(row, "selected_id") ?? pickString(row, "selectedId"),
    candidates,
    reason: pickString(row, "reason"),
  };
}
