/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { MockProductSettingsApi } from "@/lib/api/mock-product-settings-api";
import { loadProductSettings, loadReadiness, saveProductSettings } from "@/lib/api/product-settings-service";

describe("product settings service", () => {
  it("loads mock server settings", async () => {
    const api = new MockProductSettingsApi();
    const loaded = await loadProductSettings(api);
    expect(loaded.settings.version).toBe(1);
    expect(loaded.source).toBe("server");
    expect(loaded.settings.focusCourseIds).toEqual([
      "course-robots",
      "course-nn",
      "course-ml",
      "course-sec",
      "course-csdp",
    ]);
  });

  it("falls back to local cache instead of rejecting when the backend is unreachable", async () => {
    const api = new MockProductSettingsApi();
    api.getSettings = async () => {
      throw new Error("Network request failed");
    };
    const loaded = await loadProductSettings(api);
    expect(loaded.source).toBe("local_cache");
    expect(loaded.settings.version).toBe(1);
  });

  it("loads readiness without rejecting when the backend is unreachable", async () => {
    const api = new MockProductSettingsApi();
    api.getReadiness = async () => {
      throw new Error("Network request failed");
    };
    const readiness = await loadReadiness(api, { backendOk: false });
    expect(readiness.checks.some((c) => c.component === "backend" && c.status === "unavailable")).toBe(
      true,
    );
  });

  it("saves focus course ids", async () => {
    const api = new MockProductSettingsApi();
    const saved = await saveProductSettings(api, { focusCourseIds: ["x"] });
    expect(saved.settings.focusCourseIds).toEqual(["x"]);
  });
});
