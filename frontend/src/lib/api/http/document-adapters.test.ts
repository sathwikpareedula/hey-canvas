/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { AcademicApiMalformedError } from "@/lib/api/errors";
import {
  mapBackendDocumentStatus,
  mapDocumentSearchHit,
  mapDocumentSummary,
} from "@/lib/api/http/document-adapters";
import { mapDeadlineWindowToBackend as mapWindow } from "@/lib/api/http/contract-mappings";

describe("document adapters", () => {
  it("maps document summary from backend view", () => {
    const summary = mapDocumentSummary(
      {
        canvas_file_id: "file-1",
        display_name: "Lecture 1",
        filename: "lec1.pdf",
        content_type: "application/pdf",
        detected_type: "pdf",
        status: "parsed",
        parser_name: "p",
        parser_version: "1",
        source_sha256: "abc",
        parsed_at: "2026-01-01T00:00:00Z",
        unit_count: 3,
        character_count: 100,
        last_attempted_at: "2026-01-01T00:00:00Z",
        last_attempt_status: "parsed",
        last_error_category: null,
        is_stale: false,
        references: [
          {
            canvas_course_id: "c-1",
            canvas_module_id: "m-1",
            canvas_module_item_id: "i-1",
            module_name: "Week 1",
            item_title: "Slides",
          },
        ],
      },
      "Robotics",
    );
    expect(summary.documentId).toBe("file-1");
    expect(summary.ingestionState).toBe("searchable");
  });

  it("maps search hit without leaking paths", () => {
    const hit = mapDocumentSearchHit(
      {
        canvas_file_id: "file-2",
        display_name: "Notes",
        filename: "n.pdf",
        unit_type: "page",
        unit_index: 0,
        page_number: 2,
        slide_number: null,
        heading: "Intro",
        snippet: "Sample snippet",
        score: 10,
        source_sha256: "sha",
        is_stale: true,
        references: [
          {
            canvas_course_id: "c-1",
            canvas_module_id: "m",
            canvas_module_item_id: "i",
            module_name: null,
            item_title: null,
          },
        ],
      },
      "Robotics",
    );
    expect(hit.snippet).toBe("Sample snippet");
    expect(hit.isStale).toBe(true);
    expect(hit.provenance.isStale).toBe(true);
  });

  it("throws on malformed document id", () => {
    expect(() =>
      mapDocumentSummary(
        {
          canvas_file_id: "",
          display_name: null,
          filename: null,
          content_type: null,
          detected_type: null,
          status: "parsed",
          parser_name: null,
          parser_version: null,
          source_sha256: null,
          parsed_at: null,
          unit_count: 0,
          character_count: 0,
          last_attempted_at: "2026-01-01T00:00:00Z",
          last_attempt_status: "parsed",
          last_error_category: null,
          is_stale: false,
          references: [],
        },
        "Course",
      ),
    ).toThrow(AcademicApiMalformedError);
  });

  it("maps needs_ocr status", () => {
    expect(mapBackendDocumentStatus("needs_ocr")).toBe("failed");
  });
});

describe("deadline window mapping", () => {
  it("maps past_due_time to overdue", () => {
    expect(mapWindow("past_due_time")).toBe("overdue");
  });
});
