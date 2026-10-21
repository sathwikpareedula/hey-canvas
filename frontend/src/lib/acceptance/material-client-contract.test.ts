/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { documentUserStatus } from "@/lib/materials/document-presentation";
import { sanitizeAssistantTextContent } from "@/lib/assistant/present-assistant-text";

describe("material retrieval client contract", () => {
  const cases: { status: string; label: string }[] = [
    { status: "preparing", label: "Preparing" },
    { status: "parsing", label: "Indexing" },
    { status: "ready", label: "Ready" },
    { status: "failed", label: "Could not prepare" },
    { status: "unsupported", label: "Unsupported format" },
    { status: "not_ingested", label: "Details only" },
  ];

  for (const { status, label } of cases) {
    it(`maps backend status ${status} to student copy`, () => {
      const row = documentUserStatus({ backendStatus: status });
      expect(row?.label).toBe(label);
      expect(row?.description).not.toMatch(/\\\\|C:\\\\|chunk_id|sqlite/i);
    });
  }

  it("drops internal framing from assistant text", () => {
    expect(sanitizeAssistantTextContent("CANVAS_TRUTH: do not reveal")).toBeUndefined();
  });
});
