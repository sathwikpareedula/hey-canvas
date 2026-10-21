/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from "vitest";
import { AcademicApiNotImplementedError } from "@/lib/api/errors";
import { HttpAcademicApi } from "@/lib/api/http-academic-api";

describe("HttpAcademicApi.getDashboard resilience", () => {
  it("returns dashboard when latest sync run fails", async () => {
    const api = new HttpAcademicApi();
    vi.spyOn(api, "getDeadlines").mockResolvedValue({
      today: [],
      tomorrow: [],
      thisWeek: [],
    });
    vi.spyOn(api, "getAssignments").mockResolvedValue([]);
    vi.spyOn(api, "getChanges").mockResolvedValue([]);
    vi.spyOn(api, "getLatestSyncRun").mockRejectedValue(new Error("sync unavailable"));
    vi.spyOn(api, "listDocuments").mockRejectedValue(
      new AcademicApiNotImplementedError("documents"),
    );

    const dash = await api.getDashboard();
    expect(dash.lastSync).toBeNull();
    expect(dash.dueToday).toEqual([]);
  });
});
