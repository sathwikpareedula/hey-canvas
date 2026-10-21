/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { MockAcademicApi } from "@/lib/api/mock-academic-api";
import { AcademicApiNotFoundError } from "@/lib/api/errors";

describe("mock study session", () => {
  it("throws not_found for missing session id", async () => {
    const api = new MockAcademicApi();
    await expect(api.getStudySession("missing-id")).rejects.toBeInstanceOf(AcademicApiNotFoundError);
  });
});
