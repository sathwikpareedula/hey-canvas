import type { EvidenceReference } from "@/lib/domain/study-workflows";
import type { Provenance } from "@/lib/domain/types";

export function evidenceToProvenance(ref: EvidenceReference, courseId?: string): Provenance {
  const isMaterial = ref.authority === "professor_material";
  return {
    courseId: courseId ?? "",
    courseName: "Course",
    documentId: isMaterial ? ref.identifier : undefined,
    documentTitle: ref.locator ?? ref.identifier,
    excerpt: ref.locator ?? undefined,
    isStale: false,
  };
}
