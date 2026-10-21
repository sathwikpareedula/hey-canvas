import type { ProductSettingsApi } from "@/lib/api/product-settings-api";
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
import { PRODUCT_SETTINGS_API_VERSION } from "@/lib/domain/product-settings";
import { MOCK_COURSES } from "@/lib/api/mock/data";

const demoSettings: ProductSettings = {
  version: PRODUCT_SETTINGS_API_VERSION,
  focusCourseIds: MOCK_COURSES.map((course) => course.id),
  termHint: "Spring 2026",
  aiProcessingMode: "local",
  localModelTier: "recommended",
  privacyCloudOptInAcknowledged: false,
  updatedAt: new Date().toISOString(),
};

const workspaces = new Map<string, CourseWorkspaceState>();
const policies = new Map<string, CourseAiPolicySettings>();

export class MockProductSettingsApi implements ProductSettingsApi {
  private settings = { ...demoSettings };

  async getSettings(): Promise<ProductSettings | null> {
    return this.settings;
  }

  async saveSettings(settings: ProductSettings): Promise<ProductSettings> {
    this.settings = { ...settings, updatedAt: new Date().toISOString() };
    return this.settings;
  }

  async listCoursePolicies(): Promise<CourseAiPolicySettings[]> {
    return [...policies.values()];
  }

  async saveCoursePolicy(policy: CourseAiPolicySettings): Promise<CourseAiPolicySettings> {
    policies.set(policy.courseId, { ...policy, updatedAt: new Date().toISOString() });
    return policies.get(policy.courseId)!;
  }

  async getReadiness(): Promise<ProductReadiness | null> {
    return {
      overall: "ready",
      updatedAt: new Date().toISOString(),
      checks: [
        {
          component: "backend",
          status: "ready",
          label: "Demo backend",
          detail: "Synthetic catalog loaded",
          actionLabel: null,
        },
        {
          component: "local_ai_runtime",
          status: "ready",
          label: "Demo assistant",
          detail: "Synthetic provider",
          actionLabel: null,
        },
      ],
    };
  }

  async getCourseWorkspace(courseId: string): Promise<CourseWorkspaceState | null> {
    return workspaces.get(courseId) ?? {
      courseId,
      conversationId: null,
      lastViewedAt: null,
    };
  }

  async saveCourseWorkspace(workspace: CourseWorkspaceState): Promise<CourseWorkspaceState> {
    workspaces.set(workspace.courseId, {
      ...workspace,
      lastViewedAt: new Date().toISOString(),
    });
    return workspaces.get(workspace.courseId)!;
  }

  async resolveEntities(request: EntityDisambiguationRequest): Promise<EntityDisambiguationResult> {
    if (request.assignmentId || request.documentId) {
      return {
        outcome: "resolved",
        kind: request.assignmentId ? "assignment" : "document",
        selectedId: request.assignmentId ?? request.documentId ?? null,
        candidates: [],
        reason: null,
      };
    }
    return {
      outcome: "unresolved",
      kind: null,
      selectedId: null,
      candidates: [],
      reason: null,
    };
  }

  async executeDataLifecycle(request: DataLifecycleRequest): Promise<DataLifecycleResult> {
    if (request.confirmToken !== "CONFIRM") {
      return { ok: false, message: "Confirmation did not match." };
    }
    return { ok: true, message: `Demo: ${request.action} completed.` };
  }
}
