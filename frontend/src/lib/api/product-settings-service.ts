import { getApiMode } from "@/lib/api";
import type { ProductSettingsApi } from "@/lib/api/product-settings-api";
import { HttpProductSettingsApi } from "@/lib/api/http/http-product-settings-api";
import { MockProductSettingsApi } from "@/lib/api/mock-product-settings-api";
import type { AcademicApi } from "@/lib/api/academic-api";
import type {
  CourseAiPolicySettings,
  CourseWorkspaceState,
  EntityDisambiguationRequest,
  EntityDisambiguationResult,
  ProductReadiness,
  ProductSettings,
} from "@/lib/domain/product-settings";
import { PRODUCT_SETTINGS_API_VERSION } from "@/lib/domain/product-settings";
import { readAiPreferences, saveAiPreferences } from "@/lib/product/ai-preferences";
import {
  getCourseAiPolicy,
  readCourseAiPolicies,
  saveCourseAiPolicy,
  type CourseAiPolicyRecord,
} from "@/lib/product/course-ai-policy";
import {
  inferDominantTerm,
  readFocusCoursesSnapshot,
  saveFocusCourseIds,
  writeFocusCoursesSnapshot,
} from "@/lib/product/focus-courses";
import { PRODUCT_STORAGE_KEYS } from "@/lib/product/storage-keys";
import { coursePrimaryTitle } from "@/lib/courses/display";
import { matchCoursesFromUserText } from "@/lib/courses/course-router-client";
import { normalizeProductReadiness } from "@/lib/product/normalize-readiness";
import {
  synthesizeClientReadiness,
  type SyncProbe,
} from "@/lib/product/synthesize-readiness";

export type SettingsSource = "server" | "local_cache" | "local_fallback";

export interface LoadedProductSettings {
  settings: ProductSettings;
  source: SettingsSource;
}

const MIGRATION_FLAG = "hey-canvas-product-migrated-v1";

let productApiSingleton: ProductSettingsApi | null = null;

export function getProductSettingsApi(): ProductSettingsApi {
  if (productApiSingleton) return productApiSingleton;
  productApiSingleton =
    getApiMode() === "http" ? new HttpProductSettingsApi() : new MockProductSettingsApi();
  return productApiSingleton;
}

function localSettingsFromBrowser(): ProductSettings {
  const focus = readFocusCoursesSnapshot();
  const ai = readAiPreferences();
  return {
    version: PRODUCT_SETTINGS_API_VERSION,
    focusCourseIds: focus.focusCourseIds,
    termHint: focus.termHint,
    aiProcessingMode: ai.processingMode,
    localModelTier: ai.localModelTier,
    privacyCloudOptInAcknowledged: ai.processingMode === "local",
    updatedAt: focus.updatedAt,
  };
}

function persistLocalCache(settings: ProductSettings): void {
  saveFocusCourseIds(settings.focusCourseIds, settings.termHint);
  saveAiPreferences({
    processingMode: settings.aiProcessingMode,
    localModelTier: settings.localModelTier,
  });
  writeFocusCoursesSnapshot({
    version: 1,
    focusCourseIds: settings.focusCourseIds,
    termHint: settings.termHint,
    updatedAt: settings.updatedAt,
  });
}

function migrationDone(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(MIGRATION_FLAG) === "1";
}

function markMigrationDone(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(MIGRATION_FLAG, "1");
}

/** Load settings: server first, migrate local once, keep local cache in sync. */
export async function loadProductSettings(api: ProductSettingsApi): Promise<LoadedProductSettings> {
  let server: ProductSettings | null = null;
  try {
    server = await api.getSettings();
  } catch {
    // Backend unreachable: fall back to the local cache instead of rejecting, so the
    // app keeps rendering (found by browser E2E as an unhandled promise rejection).
    return { settings: localSettingsFromBrowser(), source: "local_cache" };
  }
  if (server) {
    persistLocalCache(server);
    if (!migrationDone()) markMigrationDone();
    return { settings: server, source: "server" };
  }

  const local = localSettingsFromBrowser();
  if (!migrationDone() && typeof window !== "undefined") {
    markMigrationDone();
    try {
      const pushed = await api.saveSettings(local);
      persistLocalCache(pushed);
      return { settings: pushed, source: "server" };
    } catch {
      /* backend not ready */
    }
  }

  return { settings: local, source: migrationDone() ? "local_cache" : "local_fallback" };
}

export async function saveProductSettings(
  api: ProductSettingsApi,
  patch: Partial<ProductSettings>,
): Promise<LoadedProductSettings> {
  const current = (await loadProductSettings(api)).settings;
  const next: ProductSettings = {
    ...current,
    ...patch,
    version: PRODUCT_SETTINGS_API_VERSION,
    updatedAt: new Date().toISOString(),
  };
  persistLocalCache(next);
  try {
    const saved = await api.saveSettings(next);
    persistLocalCache(saved);
    return { settings: saved, source: "server" };
  } catch {
    return { settings: next, source: "local_cache" };
  }
}

export async function saveFocusCourseIdsViaService(
  api: ProductSettingsApi,
  focusCourseIds: string[],
  catalogTermHint: string | null,
): Promise<LoadedProductSettings> {
  const termHint = catalogTermHint ?? inferDominantTerm([]);
  return saveProductSettings(api, { focusCourseIds, termHint });
}

export async function loadReadiness(
  api: ProductSettingsApi,
  context?: { backendOk?: boolean; syncProbe?: SyncProbe; canvasOnline?: boolean },
): Promise<ProductReadiness> {
  const client = await synthesizeClientReadiness({
    backendOk: context?.backendOk,
    sync: context?.syncProbe,
    canvasOnline: context?.canvasOnline,
  });
  let remote: ProductReadiness | null = null;
  try {
    remote = await api.getReadiness();
  } catch {
    // Unreachable backend: report client-side readiness only (it already says backend is down).
  }
  const base =
    remote && remote.checks.length > 0
      ? { ...remote, checks: [...remote.checks, ...client.checks] }
      : client;
  return normalizeProductReadiness(base, {
    backendOk: context?.backendOk,
    syncProbe: context?.syncProbe,
  });
}

export async function loadCourseWorkspace(
  api: ProductSettingsApi,
  courseId: string,
): Promise<CourseWorkspaceState> {
  const remote = await api.getCourseWorkspace(courseId);
  if (remote) return remote;
  return { courseId, conversationId: null, lastViewedAt: null };
}

export async function saveCourseWorkspaceState(
  api: ProductSettingsApi,
  workspace: CourseWorkspaceState,
): Promise<CourseWorkspaceState> {
  try {
    return await api.saveCourseWorkspace({
      ...workspace,
      lastViewedAt: new Date().toISOString(),
    });
  } catch {
    return workspace;
  }
}

export async function resolveEntitiesWithFallback(
  productApi: ProductSettingsApi,
  academicApi: AcademicApi,
  request: EntityDisambiguationRequest,
): Promise<EntityDisambiguationResult> {
  const remote = await productApi.resolveEntities(request);
  if (remote.outcome !== "unresolved" || remote.candidates.length > 0) {
    return remote;
  }
  if (remote.reason !== "server_disambiguation_unavailable" && remote.reason !== null) {
    return remote;
  }

  const routing = await academicApi.resolveCourseRouter({
    courseId: request.courseId,
    assignmentId: request.assignmentId,
    documentId: request.documentId,
    text: request.text,
    activeCourseId: request.courseId,
  });

  if (!request.courseId && request.text?.trim()) {
    const catalog = await academicApi.getCourses();
    const localMatch = matchCoursesFromUserText(request.text, catalog);
    if (localMatch.outcome === "resolved" && localMatch.courseId) {
      return {
        outcome: "resolved",
        kind: "course",
        selectedId: localMatch.courseId,
        candidates: [],
        reason: "client_course_match",
      };
    }
    if (localMatch.outcome === "ambiguous" && localMatch.candidates.length) {
      return {
        outcome: "ambiguous",
        kind: "course",
        selectedId: null,
        candidates: localMatch.candidates.map((c) => ({
          id: c.id,
          kind: "course",
          title: coursePrimaryTitle(c),
          subtitle: c.code ?? null,
          courseId: c.id,
        })),
        reason: "multiple_courses",
      };
    }
  }

  if (routing.outcome === "ambiguous" && routing.candidates.length) {
    return {
      outcome: "ambiguous",
      kind: "course",
      selectedId: null,
      candidates: routing.candidates.map((c) => ({
        id: c.courseId,
        kind: "course",
        title: c.courseName ?? c.courseCode ?? "Course",
        subtitle: c.courseCode,
        courseId: c.courseId,
      })),
      reason: routing.reason,
    };
  }

  if (request.documentId && routing.outcome === "resolved") {
    const document = await academicApi.getDocument(request.documentId);
    if (document && (!request.courseId || document.courseId === request.courseId)) {
      return {
        outcome: "resolved",
        kind: "document",
        selectedId: document.id,
        candidates: [],
        reason: "active_document_context",
      };
    }
  }

  const text = (request.text ?? "").toLowerCase();
  if (text && request.courseId) {
    const assignments = await academicApi.getAssignments({ courseId: request.courseId });
    const matches = assignments.filter((a) => {
      const t = a.title.toLowerCase();
      return text.includes(t.slice(0, Math.min(12, t.length))) || t.includes(text.slice(0, 24));
    });
    if (matches.length === 1) {
      return {
        outcome: "resolved",
        kind: "assignment",
        selectedId: matches[0]!.id,
        candidates: [],
        reason: "client_assignment_match",
      };
    }
    if (matches.length > 1) {
      return {
        outcome: "ambiguous",
        kind: "assignment",
        selectedId: null,
        candidates: matches.slice(0, 6).map((a) => ({
          id: a.id,
          kind: "assignment",
          title: a.title,
          subtitle: null,
          courseId: a.courseId,
        })),
        reason: "multiple_assignments",
      };
    }
    if (request.assignmentId) {
      const active = assignments.find((a) => a.id === request.assignmentId);
      if (active) {
        return {
          outcome: "resolved",
          kind: "assignment",
          selectedId: active.id,
          candidates: [],
          reason: "active_assignment_context",
        };
      }
    }

    const normalize = (value: string) =>
      value.toLowerCase().replace(/\.[a-z0-9]{1,8}$/i, "").replace(/[^a-z0-9]+/g, " ").trim();
    const normalizedText = normalize(text);
    const documents = await academicApi.listDocuments({ courseId: request.courseId, limit: 100 });
    const documentMatches = documents.filter((document) => {
      const title = normalize(document.title);
      return title.length >= 3 && normalizedText.includes(title);
    });
    if (documentMatches.length === 1) {
      return {
        outcome: "resolved",
        kind: "document",
        selectedId: documentMatches[0]!.documentId,
        candidates: [],
        reason: "client_document_match",
      };
    }
    if (documentMatches.length > 1) {
      return {
        outcome: "ambiguous",
        kind: "document",
        selectedId: null,
        candidates: documentMatches.slice(0, 6).map((document) => ({
          id: document.documentId,
          kind: "document",
          title: document.title,
          subtitle: document.documentType,
          courseId: document.courseId,
        })),
        reason: "multiple_documents",
      };
    }
  }

  return {
    outcome: routing.outcome === "resolved" ? "resolved" : "unresolved",
    kind: routing.course ? "course" : null,
    selectedId: routing.course?.courseId ?? null,
    candidates: [],
    reason: routing.reason,
  };
}

export async function syncCoursePolicyToServer(
  api: ProductSettingsApi,
  courseId: string,
  record: CourseAiPolicyRecord,
): Promise<void> {
  saveCourseAiPolicy(courseId, record);
  const payload: CourseAiPolicySettings = {
    courseId,
    instructorPolicy: record.instructorPolicy,
    cloudProcessing: record.cloudProcessing,
    notes: record.notes,
    updatedAt: new Date().toISOString(),
  };
  try {
    await api.saveCoursePolicy(payload);
  } catch {
    /* local record already saved */
  }
}

export function loadLocalCoursePolicies(): Record<string, CourseAiPolicyRecord> {
  return readCourseAiPolicies();
}

export function getLocalCoursePolicy(courseId: string): CourseAiPolicyRecord {
  return getCourseAiPolicy(courseId);
}

export const APPROVED_PRODUCT_STORAGE_KEYS = [
  PRODUCT_STORAGE_KEYS.onboarding,
  PRODUCT_STORAGE_KEYS.focusCourses,
  PRODUCT_STORAGE_KEYS.aiPreferences,
  PRODUCT_STORAGE_KEYS.courseAiPolicies,
  MIGRATION_FLAG,
];
