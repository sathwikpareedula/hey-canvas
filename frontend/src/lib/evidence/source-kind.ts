import type { Provenance } from "@/lib/domain/types";

export type EvidenceSourceKind =
  | "canvas"
  | "assignment_instructions"
  | "professor_material"
  | "module"
  | "change"
  | "ai_explanation"
  | "unknown";

export function inferEvidenceSourceKind(provenance: Provenance): EvidenceSourceKind {
  const docType = (provenance as { documentType?: string }).documentType;
  if (docType === "assignment") return "assignment_instructions";
  if (provenance.documentTitle || provenance.fileName) return "professor_material";
  if (provenance.moduleItemTitle || provenance.moduleName) return "module";
  if (provenance.excerpt && !provenance.documentTitle) return "change";
  if (provenance.courseName && !provenance.documentTitle && !provenance.fileName) return "canvas";
  return "unknown";
}

export function evidenceSourceKindLabel(kind: EvidenceSourceKind): string {
  switch (kind) {
    case "canvas":
      return "Canvas";
    case "assignment_instructions":
      return "Assignment instructions";
    case "professor_material":
      return "Professor material";
    case "ai_explanation":
      return "AI explanation";
    case "module":
      return "Module item";
    case "change":
      return "Recent change";
    default:
      return "Source";
  }
}
