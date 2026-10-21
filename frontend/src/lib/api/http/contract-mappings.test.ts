/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  mapBackendStudyModeToUi,
  mapDeadlineWindowToBackend,
  mapUiStudyModeToBackend,
} from "@/lib/api/http/contract-mappings";

describe("contract mappings", () => {
  it("maps overdue backend window", () => {
    expect(mapDeadlineWindowToBackend("past_due_time")).toBe("overdue");
  });

  it("maps exam_prep to exam UI mode", () => {
    expect(mapBackendStudyModeToUi("exam_prep")).toBe("exam");
  });

  it("maps exam UI mode to exam_prep", () => {
    expect(mapUiStudyModeToBackend("exam")).toBe("exam_prep");
  });
});
