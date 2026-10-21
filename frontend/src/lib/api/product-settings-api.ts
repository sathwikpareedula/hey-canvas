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

/** Typed boundary for product-settings backend resources. */
export interface ProductSettingsApi {
  getSettings(): Promise<ProductSettings | null>;
  saveSettings(settings: ProductSettings): Promise<ProductSettings>;
  listCoursePolicies(): Promise<CourseAiPolicySettings[]>;
  saveCoursePolicy(policy: CourseAiPolicySettings): Promise<CourseAiPolicySettings>;
  getReadiness(): Promise<ProductReadiness | null>;
  getCourseWorkspace(courseId: string): Promise<CourseWorkspaceState | null>;
  saveCourseWorkspace(workspace: CourseWorkspaceState): Promise<CourseWorkspaceState>;
  resolveEntities(request: EntityDisambiguationRequest): Promise<EntityDisambiguationResult>;
  executeDataLifecycle(request: DataLifecycleRequest): Promise<DataLifecycleResult>;
}
