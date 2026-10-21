/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { documentUserStatus } from "@/lib/materials/document-presentation";

describe("documentUserStatus", () => {
  it("labels ready materials", () => {
    expect(documentUserStatus({ ingestionState: "searchable" })?.label).toBe("Ready");
  });

  it("labels unsupported", () => {
    expect(documentUserStatus({ backendStatus: "unsupported" })?.label).toBe(
      "Unsupported format",
    );
  });
});
