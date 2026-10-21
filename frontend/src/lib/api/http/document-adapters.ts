import { AcademicApiMalformedError } from "@/lib/api/errors";
import type {
  DocumentDetail,
  DocumentIngestionState,
  DocumentSearchResult,
  DocumentSummary,
  DocumentType,
  DocumentUnit,
  Provenance,
} from "@/lib/domain/types";

export interface BackendFileReference {
  canvas_course_id: string;
  canvas_module_id: string;
  canvas_module_item_id: string;
  module_name: string | null;
  item_title: string | null;
}

export interface BackendDocumentView {
  canvas_file_id: string;
  display_name: string | null;
  filename: string | null;
  content_type: string | null;
  detected_type: string | null;
  status: string;
  parser_name: string | null;
  parser_version: string | null;
  source_sha256: string | null;
  parsed_at: string | null;
  unit_count: number;
  character_count: number;
  last_attempted_at: string;
  last_attempt_status: string;
  last_error_category: string | null;
  is_stale: boolean;
  references: BackendFileReference[];
}

export interface BackendDocumentUnitView {
  canvas_file_id: string;
  source_sha256: string | null;
  parser_name: string | null;
  parser_version: string | null;
  unit_type: string;
  unit_index: number;
  page_number: number | null;
  slide_number: number | null;
  heading: string | null;
  text: string;
  text_fingerprint: string;
  character_count: number;
  references: BackendFileReference[];
}

export interface BackendDocumentSearchHit {
  canvas_file_id: string;
  display_name: string | null;
  filename: string | null;
  unit_type: string;
  unit_index: number;
  page_number: number | null;
  slide_number: number | null;
  heading: string | null;
  snippet: string;
  score: number;
  source_sha256: string;
  is_stale: boolean;
  references: BackendFileReference[];
}

function requireFileId(row: BackendDocumentView | BackendDocumentSearchHit): string {
  if (!row?.canvas_file_id || typeof row.canvas_file_id !== "string") {
    throw new AcademicApiMalformedError("Document row missing canvas_file_id");
  }
  return row.canvas_file_id;
}

function primaryReference(refs: BackendFileReference[] | undefined): BackendFileReference | null {
  if (!refs?.length) return null;
  const ref = refs[0];
  if (!ref?.canvas_course_id) return null;
  return ref;
}

export function mapBackendDocumentType(detected: string | null | undefined): DocumentType {
  switch (detected) {
    case "pdf":
      return "pdf";
    case "pptx":
      return "slides";
    case "docx":
    case "markdown":
    case "text":
      return "notes";
    default:
      return "other";
  }
}

export function mapBackendDocumentTypeToQuery(
  documentType: DocumentType,
): string | undefined {
  switch (documentType) {
    case "pdf":
      return "pdf";
    case "slides":
      return "pptx";
    case "notes":
      return "docx";
    default:
      return undefined;
  }
}

export function mapBackendDocumentStatus(status: string): DocumentIngestionState {
  switch (status) {
    case "parsed":
      return "searchable";
    case "needs_ocr":
      return "failed";
    case "failed":
    case "unsupported":
    case "source_missing":
    case "source_corrupt":
      return "failed";
    case "not_ingested":
    case "download_required":
    default:
      return "pending";
  }
}

function unitLabel(unit: {
  page_number: number | null;
  slide_number: number | null;
  heading: string | null;
  unit_index: number;
  unit_type: string;
}): string {
  if (unit.page_number != null) return `Page ${unit.page_number}`;
  if (unit.slide_number != null) return `Slide ${unit.slide_number}`;
  if (unit.heading) return unit.heading;
  return `${unit.unit_type} ${unit.unit_index + 1}`;
}

export function mapUnitFromBackend(unit: BackendDocumentUnitView): DocumentUnit {
  return {
    label: unitLabel(unit),
    page: unit.page_number ?? undefined,
    slide: unit.slide_number ?? undefined,
    section: unit.heading ?? undefined,
  };
}

export function mapProvenanceFromReferences(
  refs: BackendFileReference[],
  courseName: string,
  extras?: {
    documentTitle?: string;
    fileName?: string;
    unit?: DocumentUnit;
    excerpt?: string;
    isStale?: boolean;
  },
): Provenance {
  const ref = primaryReference(refs);
  return {
    courseId: ref?.canvas_course_id ?? "unknown",
    courseName,
    moduleName: ref?.module_name ?? undefined,
    moduleItemTitle: ref?.item_title ?? undefined,
    fileName: extras?.fileName ?? undefined,
    documentTitle: extras?.documentTitle ?? undefined,
    unit: extras?.unit,
    excerpt: extras?.excerpt,
    isStale: extras?.isStale,
  };
}

export function mapDocumentSummary(
  row: BackendDocumentView,
  courseName: string,
): DocumentSummary {
  const id = requireFileId(row);
  const ref = primaryReference(row.references);
  return {
    documentId: id,
    title: row.display_name ?? row.filename ?? "Untitled material",
    courseId: ref?.canvas_course_id ?? "unknown",
    courseName,
    documentType: mapBackendDocumentType(row.detected_type),
    ingestionState: mapBackendDocumentStatus(row.status),
    isStale: Boolean(row.is_stale),
    needsOcr: row.status === "needs_ocr",
    unitCount: row.unit_count,
    backendStatus: row.status,
  };
}

export function primaryCourseIdFromDocument(row: BackendDocumentView): string | undefined {
  return primaryReference(row.references)?.canvas_course_id;
}

export function primaryCourseIdFromRefs(
  refs: BackendFileReference[] | undefined,
): string | undefined {
  return primaryReference(refs)?.canvas_course_id;
}

export function mapDocumentSearchHit(
  hit: BackendDocumentSearchHit,
  courseName: string,
): DocumentSearchResult {
  const id = requireFileId(hit);
  const unit: DocumentUnit = {
    label: unitLabel(hit),
    page: hit.page_number ?? undefined,
    slide: hit.slide_number ?? undefined,
    section: hit.heading ?? undefined,
  };
  const provenance = mapProvenanceFromReferences(hit.references, courseName, {
    documentTitle: hit.display_name ?? hit.filename ?? undefined,
    fileName: hit.filename ?? undefined,
    unit,
    excerpt: hit.snippet,
    isStale: hit.is_stale,
  });
  return {
    documentId: id,
    title: hit.display_name ?? hit.filename ?? "Material",
    courseId: provenance.courseId,
    courseName,
    snippet: hit.snippet,
    unit,
    provenance,
    documentType: mapBackendDocumentType(null),
    isStale: hit.is_stale,
  };
}

export function mapDocumentSummaryToBrowseResult(
  summary: DocumentSummary,
): DocumentSearchResult {
  const provenance = mapProvenanceFromReferences(
    [],
    summary.courseName,
    {
      documentTitle: summary.title,
      isStale: summary.isStale,
    },
  );
  provenance.courseId = summary.courseId;
  const snippet = summary.needsOcr
    ? "This file has no searchable text yet. Grounded search and chat need optional OCR before it can be used as evidence."
    : summary.ingestionState === "searchable"
      ? `${summary.unitCount} unit(s) indexed`
      : `Status: ${summary.backendStatus}`;
  return {
    documentId: summary.documentId,
    title: summary.title,
    courseId: summary.courseId,
    courseName: summary.courseName,
    snippet,
    unit: { label: "Document overview" },
    provenance,
    documentType: summary.documentType,
    isStale: summary.isStale,
  };
}

export function mapDocumentDetail(
  row: BackendDocumentView,
  courseName: string,
  units: BackendDocumentUnitView[],
  previewText?: string,
): DocumentDetail {
  const id = requireFileId(row);
  const provenance = mapProvenanceFromReferences(row.references, courseName, {
    documentTitle: row.display_name ?? row.filename ?? undefined,
    fileName: row.filename ?? undefined,
    isStale: row.is_stale,
  });
  const mappedUnits = units.map(mapUnitFromBackend);
  const firstUnitText = units[0]?.text?.slice(0, 1200);
  return {
    id,
    courseId: provenance.courseId,
    courseName,
    title: row.display_name ?? row.filename ?? "Untitled material",
    documentType: mapBackendDocumentType(row.detected_type),
    provenance,
    previewPlainText:
      previewText ??
      firstUnitText ??
      (row.status === "parsed"
        ? "No preview text available for this document."
        : "This document is not parsed yet."),
    ingestionState: mapBackendDocumentStatus(row.status),
    units: mappedUnits.length ? mappedUnits : undefined,
    isStale: row.is_stale,
    needsOcr: row.status === "needs_ocr",
    backendStatus: row.status,
    technical: {
      contentSha256: row.source_sha256 ?? undefined,
      parserVersion: row.parser_version ?? undefined,
    },
  };
}
