"use client";

import { useSourceDrawer } from "@/contexts/SourceDrawerContext";
import type { EvidenceReference } from "@/lib/domain/study-workflows";
import { evidenceToProvenance } from "@/lib/evidence/open-evidence";

export function EvidenceRefButton({
  evidence,
  courseId,
}: {
  evidence: EvidenceReference;
  courseId?: string;
}) {
  const { openSource } = useSourceDrawer();
  if (evidence.authority !== "professor_material") {
    return (
      <span className="text-xs text-[var(--muted)]">
        {evidence.locator ?? evidence.identifier}
      </span>
    );
  }
  return (
    <button
      type="button"
      className="text-xs text-[var(--accent)] underline"
      onClick={() => openSource(evidenceToProvenance(evidence, courseId))}
    >
      {evidence.locator ?? "Open material evidence"}
    </button>
  );
}
