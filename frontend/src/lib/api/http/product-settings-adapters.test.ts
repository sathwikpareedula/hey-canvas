/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapBackendDisambiguation,
  mapBackendProductSettings,
  mapProductSettingsToBackend,
} from "@/lib/api/http/product-settings-adapters";

describe("product settings adapters", () => {
  it("maps snake_case settings", () => {
    const settings = mapBackendProductSettings({
      version: 1,
      focus_course_ids: ["c1", "c2"],
      term_hint: "Fall 2026",
      ai_processing_mode: "local",
      local_model_tier: "lightweight",
      updated_at: "2026-01-01T00:00:00Z",
    });
    expect(settings.focusCourseIds).toEqual(["c1", "c2"]);
    expect(settings.localModelTier).toBe("lightweight");
  });

  it("round-trips to backend body", () => {
    const settings = mapBackendProductSettings({
      focus_course_ids: ["a"],
      ai_processing_mode: "cloud",
    });
    const body = mapProductSettingsToBackend(settings);
    expect(body.focus_course_ids).toEqual(["a"]);
    expect(body.ai_processing_mode).toBe("cloud");
  });

  it("maps disambiguation candidates", () => {
    const result = mapBackendDisambiguation({
      outcome: "ambiguous",
      kind: "assignment",
      candidates: [{ id: "a1", kind: "assignment", title: "Report" }],
    });
    expect(result.outcome).toBe("ambiguous");
    expect(result.candidates[0]?.title).toBe("Report");
  });
});
