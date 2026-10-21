import type {
  Assignment,
  AssistantSource,
  ChangeEvent,
  Course,
  DocumentUnit,
} from "@/lib/domain/types";

type JsonRecord = Record<string, unknown>;

export function mapToolAssignmentRecord(row: JsonRecord): Assignment | null {
  const id = row.canvas_assignment_id;
  const courseId = row.canvas_course_id;
  if (typeof id !== "string" || typeof courseId !== "string") return null;
  return {
    id,
    courseId,
    title: typeof row.name === "string" ? row.name : "Assignment",
    dueAt: typeof row.due_at === "string" ? row.due_at : null,
    pointsPossible: typeof row.points_possible === "number" ? row.points_possible : null,
    workflowState: typeof row.workflow_state === "string" ? row.workflow_state : null,
    published: typeof row.published === "boolean" ? row.published : null,
  };
}

export function mapDeadlineGroupPayload(payload: JsonRecord | null | undefined): Assignment[] {
  const list = payload?.assignments;
  if (!Array.isArray(list)) return [];
  return list
    .map((item) => (item && typeof item === "object" ? mapToolAssignmentRecord(item as JsonRecord) : null))
    .filter((a): a is Assignment => a !== null);
}

export function mapAssignmentContextPayload(
  payload: JsonRecord | null | undefined,
): { assignments: Assignment[]; course?: Course; summary?: string } {
  if (!payload) return { assignments: [] };
  const assignment = payload.assignment;
  const course = payload.course;
  const assignments =
    assignment && typeof assignment === "object"
      ? [mapToolAssignmentRecord(assignment as JsonRecord)].filter((a): a is Assignment => Boolean(a))
      : [];
  const courseView =
    course && typeof course === "object" && typeof (course as JsonRecord).canvas_course_id === "string"
      ? {
          id: String((course as JsonRecord).canvas_course_id),
          name: String((course as JsonRecord).course_name ?? "Course"),
          code:
            typeof (course as JsonRecord).course_code === "string"
              ? String((course as JsonRecord).course_code)
              : undefined,
        }
      : undefined;
  const name =
    assignment && typeof assignment === "object" && typeof (assignment as JsonRecord).name === "string"
      ? String((assignment as JsonRecord).name)
      : undefined;
  return { assignments, course: courseView, summary: name };
}

export function mapChangeEventRecord(row: JsonRecord): ChangeEvent | null {
  if (typeof row.id !== "number" && typeof row.id !== "string") return null;
  const ctx = row.context && typeof row.context === "object" ? (row.context as JsonRecord) : null;
  const label =
    (ctx?.label as string | undefined) ??
    (typeof row.entity_external_id === "string" ? row.entity_external_id : "Change");
  return {
    id: String(row.id),
    observedAt: typeof row.observed_at === "string" ? row.observed_at : new Date().toISOString(),
    courseId: typeof row.course_canvas_id === "string" ? row.course_canvas_id : null,
    entityType: typeof row.entity_type === "string" ? row.entity_type : "entity",
    entityLabel: label,
    eventType: typeof row.event_type === "string" ? row.event_type : "changed",
    fieldName: typeof row.field_name === "string" ? row.field_name : null,
    oldValue: row.old_value != null ? String(row.old_value) : null,
    newValue: row.new_value != null ? String(row.new_value) : null,
  };
}

export function mapRecentChangesPayload(payload: JsonRecord | null | undefined): ChangeEvent[] {
  const changes = payload?.changes;
  if (!Array.isArray(changes)) return [];
  return changes
    .map((c) => (c && typeof c === "object" ? mapChangeEventRecord(c as JsonRecord) : null))
    .filter((c): c is ChangeEvent => c !== null);
}

export function mapDocumentEvidenceFromRecord(row: JsonRecord): AssistantSource | null {
  const id = row.canvas_file_id;
  if (typeof id !== "string") return null;
  const hasUnit =
    typeof row.unit_type === "string" ||
    typeof row.page_number === "number" ||
    typeof row.slide_number === "number" ||
    typeof row.heading === "string";
  const unit: DocumentUnit | undefined = hasUnit
    ? {
        label: typeof row.unit_type === "string" ? row.unit_type : "location",
        page: typeof row.page_number === "number" ? row.page_number : undefined,
        slide: typeof row.slide_number === "number" ? row.slide_number : undefined,
        section: typeof row.heading === "string" ? row.heading : undefined,
      }
    : undefined;
  return {
    id,
    provenance: {
      courseId: typeof row.canvas_course_id === "string" ? row.canvas_course_id : "",
      courseName: "Course",
      documentId: id,
      documentTitle:
        typeof row.display_name === "string"
          ? row.display_name
          : typeof row.filename === "string"
            ? row.filename
            : id,
      fileName: typeof row.filename === "string" ? row.filename : undefined,
      unit,
      excerpt: typeof row.excerpt === "string" ? row.excerpt : undefined,
      isStale: Boolean(row.is_stale),
    },
  };
}

export function mapEvidenceReferences(
  references: { authority: string; identifier: string; locator?: string | null }[] | undefined,
  evidenceRows?: JsonRecord[],
): AssistantSource[] {
  const byId = new Map<string, JsonRecord>();
  for (const row of evidenceRows ?? []) {
    if (typeof row.canvas_file_id === "string") byId.set(row.canvas_file_id, row);
  }
  if (!references?.length) return [];
  const unique = new Set<string>();
  return references
    .filter((ref) => {
      const key = `${ref.authority}:${ref.identifier}`;
      if (unique.has(key)) return false;
      unique.add(key);
      return true;
    })
    .map((ref) => {
      const full = byId.get(ref.identifier);
      if (full) return mapDocumentEvidenceFromRecord(full);
      const title = ref.locator?.trim();
      return {
        id: ref.identifier,
        provenance: {
          courseId: "",
          courseName: "Course",
          documentId: ref.authority === "professor_material" ? ref.identifier : undefined,
          documentTitle: title && title !== ref.identifier ? title : "Course source",
          isStale: false,
        },
      };
    })
    .filter((source): source is AssistantSource => source !== null);
}
