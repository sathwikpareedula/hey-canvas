/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapAssignmentContextPayload,
  mapDeadlineGroupPayload,
  mapDocumentEvidenceFromRecord,
  mapEvidenceReferences,
} from "@/lib/api/http/assistant-block-payloads";

describe("assistant block payloads", () => {
  it("maps deadline_group assignments", () => {
    const assignments = mapDeadlineGroupPayload({
      assignments: [
        {
          canvas_assignment_id: "a1",
          canvas_course_id: "c1",
          name: "Lab 2",
          due_at: "2026-10-01T00:00:00Z",
        },
      ],
    });
    expect(assignments).toHaveLength(1);
    expect(assignments[0]?.id).toBe("a1");
    expect(assignments[0]?.title).toBe("Lab 2");
  });

  it("maps assignment context course and assignment", () => {
    const ctx = mapAssignmentContextPayload({
      assignment: {
        canvas_assignment_id: "a1",
        canvas_course_id: "c1",
        name: "HW 1",
      },
      course: {
        canvas_course_id: "c1",
        course_name: "Robotics",
      },
    });
    expect(ctx.assignments[0]?.title).toBe("HW 1");
    expect(ctx.course?.name).toBe("Robotics");
  });

  it("maps document evidence provenance", () => {
    const source = mapDocumentEvidenceFromRecord({
      canvas_file_id: "f1",
      canvas_course_id: "c1",
      display_name: "Lecture 3",
      page_number: 4,
      excerpt: "Sample",
      is_stale: true,
    });
    expect(source?.provenance.documentId).toBe("f1");
    expect(source?.provenance.isStale).toBe(true);
    expect(source?.provenance.unit?.page).toBe(4);
  });
  it("deduplicates repeated document references and uses readable titles", () => {
    const sources = mapEvidenceReferences([
      { authority: "professor_material", identifier: "44065033", locator: "Lecture 01.pdf" },
      { authority: "professor_material", identifier: "44065033", locator: "Lecture 01.pdf" },
      { authority: "professor_material", identifier: "43938818", locator: "Hoshen-Kopelman.pdf" },
    ]);
    expect(sources).toHaveLength(2);
    expect(sources[0]?.provenance.documentTitle).toBe("Lecture 01.pdf");
    expect(sources[1]?.provenance.documentTitle).toBe("Hoshen-Kopelman.pdf");
  });

  it("does not show raw Canvas IDs as document titles", () => {
    const [source] = mapEvidenceReferences([
      { authority: "professor_material", identifier: "44065033" },
    ]);
    expect(source.provenance.documentTitle).toBe("Course source");
    expect(source.provenance.documentId).toBe("44065033");
  });

  it("maps the deterministic assignment citation payload as a visible course card", () => {
    const ctx = mapAssignmentContextPayload({
      assignment: {
        canvas_assignment_id: "2393399",
        canvas_course_id: "278791",
        name: "Quiz 3",
        due_at: "2026-10-20T21:00:00+00:00",
      },
      course: {
        canvas_course_id: "278791",
        course_name: "Autonomous Robots",
      },
    });
    expect(ctx.assignments).toHaveLength(1);
    expect(ctx.assignments[0]?.id).toBe("2393399");
    expect(ctx.course?.name).toBe("Autonomous Robots");
  });

});
