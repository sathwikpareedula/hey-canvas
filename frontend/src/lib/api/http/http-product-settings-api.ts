import type { ProductSettingsApi } from "@/lib/api/product-settings-api";
import { AcademicApiError } from "@/lib/api/errors";
import { fetchJson, postJson, putJson } from "@/lib/api/http/fetch-json";
import {
  mapBackendCoursePolicy,
  mapBackendDisambiguation,
  mapBackendProductSettings,
  mapBackendReadiness,
  mapBackendWorkspace,
  mapCoursePolicyToBackend,
  mapWorkspaceToBackend,
} from "@/lib/api/http/product-settings-adapters";
import { resolveApiBaseUrl } from "@/lib/api/resolve-api-base-url";
import type {
  CourseAiPolicySettings,
  CourseWorkspaceState,
  DataLifecycleRequest,
  DataLifecycleResult,
  EntityDisambiguationRequest,
  EntityDisambiguationResult,
  ProductReadiness,
  ProductSettings,
} from "@/lib/domain/product-settings";

function base(): string {
  return resolveApiBaseUrl();
}

async function tryGet<T>(path: string, map: (row: Record<string, unknown>) => T): Promise<T | null> {
  try {
    const row = await fetchJson<Record<string, unknown>>(`${base()}${path}`);
    return map(row);
  } catch (err) {
    if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) {
      return null;
    }
    throw err;
  }
}

export class HttpProductSettingsApi implements ProductSettingsApi {
  async getSettings(): Promise<ProductSettings | null> {
    try {
      const [focus, privacy] = await Promise.all([
        fetchJson<Record<string, unknown>[]>(`${base()}/api/focus-courses`),
        fetchJson<Record<string, unknown>>(`${base()}/api/privacy`),
      ]);
      return mapBackendProductSettings({
        focus_course_ids: focus
          .map((item) => item.course_id)
          .filter((id): id is string => typeof id === "string"),
        ai_processing_mode: privacy.mode === "OPTIONAL_CLOUD_BYO" ? "cloud" : "local",
        privacy_cloud_opt_in_acknowledged: privacy.mode === "OPTIONAL_CLOUD_BYO",
        updated_at: privacy.updated_at,
      });
    } catch (err) {
      if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) return null;
      throw err;
    }
  }

  async saveSettings(settings: ProductSettings): Promise<ProductSettings> {
    await Promise.all([
      putJson<Record<string, unknown>[]>(`${base()}/api/focus-courses`, {
        course_ids: settings.focusCourseIds,
      }),
      putJson<Record<string, unknown>>(`${base()}/api/privacy`, {
        mode: settings.aiProcessingMode === "cloud" ? "OPTIONAL_CLOUD_BYO" : "LOCAL_ONLY",
      }),
    ]);
    return settings;
  }

  async listCoursePolicies(): Promise<CourseAiPolicySettings[]> {
    try {
      const focus = await fetchJson<Record<string, unknown>[]>(`${base()}/api/focus-courses`);
      return Promise.all(
        focus
          .map((item) => item.course_id)
          .filter((id): id is string => typeof id === "string")
          .map(async (courseId) =>
            mapBackendCoursePolicy(
              await fetchJson<Record<string, unknown>>(
                `${base()}/api/privacy/courses/${encodeURIComponent(courseId)}`,
              ),
            ),
          ),
      );
    } catch (err) {
      if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) {
        return [];
      }
      throw err;
    }
  }

  async saveCoursePolicy(policy: CourseAiPolicySettings): Promise<CourseAiPolicySettings> {
    const row = await putJson<Record<string, unknown>>(
      `${base()}/api/privacy/courses/${encodeURIComponent(policy.courseId)}`,
      mapCoursePolicyToBackend(policy),
    );
    return mapBackendCoursePolicy(row);
  }

  async getReadiness(): Promise<ProductReadiness | null> {
    return tryGet("/api/readiness", mapBackendReadiness);
  }

  async getCourseWorkspace(courseId: string): Promise<CourseWorkspaceState | null> {
    try {
      const rows = await fetchJson<Record<string, unknown>[]>(
        `${base()}/api/workspaces?course_id=${encodeURIComponent(courseId)}`,
      );
      return rows[0] ? mapBackendWorkspace(rows[0]) : null;
    } catch (err) {
      if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) return null;
      throw err;
    }
  }

  async saveCourseWorkspace(workspace: CourseWorkspaceState): Promise<CourseWorkspaceState> {
    const key = `course:${workspace.courseId}`;
    await postJson<Record<string, unknown>>(
      `${base()}/api/workspaces/${encodeURIComponent(key)}?course_id=${encodeURIComponent(workspace.courseId)}`,
      {},
    );
    const row = await putJson<Record<string, unknown>>(
      `${base()}/api/workspaces/${encodeURIComponent(key)}`,
      mapWorkspaceToBackend(workspace),
    );
    return mapBackendWorkspace(row);
  }

  async resolveEntities(request: EntityDisambiguationRequest): Promise<EntityDisambiguationResult> {
    try {
      const row = await postJson<Record<string, unknown>>(
        `${base()}/api/product/disambiguation/resolve`,
        {
          text: request.text,
          course_id: request.courseId,
          assignment_id: request.assignmentId,
          document_id: request.documentId,
          intent: request.intent,
        },
      );
      return mapBackendDisambiguation(row);
    } catch (err) {
      if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) {
        return {
          outcome: "unresolved",
          kind: null,
          selectedId: null,
          candidates: [],
          reason: "server_disambiguation_unavailable",
        };
      }
      throw err;
    }
  }

  async executeDataLifecycle(request: DataLifecycleRequest): Promise<DataLifecycleResult> {
    if (
      request.action === "clear_assistant_context" ||
      request.action === "clear_study_sessions" ||
      request.action === "clear_practice_sessions" ||
      request.action === "clear_local_index"
    ) {
      return { ok: true, message: "Local browser state cleared." };
    }
    if (request.action === "disconnect_canvas" || !request.courseId) {
      return { ok: false, message: "This action is not available from the browser." };
    }
    try {
      const row = await postJson<Record<string, unknown>>(`${base()}/api/lifecycle/clear`, {
        workspace_key: `course:${request.courseId}`,
        course_id: request.courseId,
      });
      return {
        ok: Boolean(row.workspace_deleted),
        message: Boolean(row.workspace_deleted)
          ? "Course workspace cleared."
          : "No course workspace was stored.",
      };
    } catch (err) {
      if (err instanceof AcademicApiError && (err.status === 404 || err.status === 501)) {
        return { ok: false, message: "This action is not available until the backend is updated." };
      }
      throw err;
    }
  }
}
